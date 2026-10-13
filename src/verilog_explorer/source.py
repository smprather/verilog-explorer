"""Resolve a cell's recorded source range against the files on disk.

WHY THIS EXISTS. `src` is the only link from a synthesised cell back to the line a
human wrote, and it is easy to make that link lie.

A `src` value is a path *relative to the directory synthesis ran in* — `rtl/pe_ctrl.v`
— so it resolves as `src_root / src_path` and by nothing else. Matching on the
basename would happily find a `pe_ctrl.v` somewhere else, and a link to the wrong
file is worse than no link.

A range can also outlive its file: in the reference design, six `.ys` snapshots under
`reviews/` no longer match the tree they described, and a source pane scrolled to a
stale range is exactly the failure this tool exists to prevent. So a range that runs
past the end of the file says so.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: `rtl/pe_ctrl.v:636.3-1326.6` — yosys records line.column pairs for both ends.
SRC_RE = re.compile(
    r"^(?P<path>.+?):(?P<first_line>\d+)\.(?P<first_col>\d+)"
    r"-(?P<last_line>\d+)\.(?P<last_col>\d+)$"
)

DRIFT_TEMPLATE = (
    "{path} has {found} lines, but the netlist points at line {wanted}: "
    "the file on disk is not the revision this netlist was built from"
)


@dataclass(frozen=True, slots=True)
class Location:
    """A resolved source range: a file, and the lines the cell came from."""

    path: Path
    first_line: int
    last_line: int
    raw: str


def parse_src(value: str | None) -> tuple[str, int, int] | None:
    """`(path, first_line, last_line)` from a `src` string, or None."""
    if not value:
        return None
    match = SRC_RE.match(value.strip())
    if not match:
        return None
    return match["path"], int(match["first_line"]), int(match["last_line"])


class SourceIndex:
    """Files, resolved against the root that the recorded `src` paths are relative to.

    With no root — or with a `src` that does not parse, or a file that is not there —
    every method answers `None` rather than raising: a netlist is readable without its
    RTL, so a missing source is a thing to say in the pane, not a failure of the run.
    """

    def __init__(self, src_root: Path | str | None = None) -> None:
        self.src_root = Path(src_root) if src_root is not None else None
        self._cache: dict[Path, list[str] | None] = {}

    def locate(self, src: str | None) -> Location | None:
        parsed = parse_src(src)
        if parsed is None or self.src_root is None:
            return None
        relative, first_line, last_line = parsed
        path = self.src_root / relative
        if not path.is_file():
            return None
        return Location(path=path, first_line=first_line, last_line=last_line, raw=src or "")

    def lines(self, path: Path) -> list[str] | None:
        """The file's lines, read once. `None` when it cannot be read."""
        if path in self._cache:
            return self._cache[path]
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            self._cache[path] = None
            return None
        lines = text.splitlines()
        self._cache[path] = lines
        return lines

    def drift(self, src: str | None) -> str | None:
        """A sentence when the file on disk is not the file the netlist came from."""
        location = self.locate(src)
        if location is None:
            return None
        lines = self.lines(location.path)
        if lines is None:
            return None
        if location.last_line > len(lines):
            return DRIFT_TEMPLATE.format(
                path=location.path, found=len(lines), wanted=location.last_line
            )
        return None
