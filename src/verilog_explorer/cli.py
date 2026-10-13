"""Command line: one netlist in, one page out.

WHY THIS EXISTS. The exit codes are the contract. A gate needs to tell "the page on
disk is stale" from "this design has latches" from "I could not read the input", and
the only way to get that right is to keep findings *out* of the exit code: the
reference design has latches, four register files and twenty dead nets by
construction, so a nonzero exit for any of those would make the command useless the
first time it ran.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from verilog_explorer.load import NotANetlistError, load_design
from verilog_explorer.render import render_html, source_coverage
from verilog_explorer.source import SourceIndex

#: Rendered. Findings are content and never change this.
EXIT_OK = 0
#: `--check` found the file on disk does not match the netlist.
EXIT_STALE = 1
#: Could not complete: bad input, or a `--src-root` that resolves nothing.
EXIT_INCOMPLETE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verilog-explorer",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("netlist", type=Path, help="a yosys JSON netlist (write_json)")
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=None,
        help="HTML file to write (default: <netlist>.html)",
    )
    parser.add_argument(
        "--src-root",
        type=Path,
        default=None,
        help=("the directory synthesis ran in; the netlist's src paths are relative to it"),
    )
    parser.add_argument("--title", default=None, help="page title")
    parser.add_argument(
        "--check",
        action="store_true",
        help="render in memory and compare with the file; write nothing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out = args.out or args.netlist.with_suffix(".html")

    try:
        design = load_design(args.netlist)
    except NotANetlistError as exc:
        print(f"cannot complete: {exc}", file=sys.stderr)
        return EXIT_INCOMPLETE

    sources = SourceIndex(args.src_root) if args.src_root is not None else None
    if sources is not None:
        claimed, resolved = source_coverage(design, sources)
        if claimed and not resolved:
            print(
                f"cannot complete: no source file resolved under --src-root "
                f"{args.src_root} ({resolved} of {claimed} recorded paths); the "
                "netlist's src paths are relative to the directory synthesis ran in",
                file=sys.stderr,
            )
            return EXIT_INCOMPLETE

    page = render_html(design, sources=sources, title=args.title)

    if args.check:
        if out.is_file() and out.read_text(encoding="utf-8") == page:
            print(f"ok: {out} matches the netlist")
            return EXIT_OK
        print(f"stale: {out} does not match the netlist; rerun without --check")
        return EXIT_STALE

    out.write_text(page, encoding="utf-8")
    print(f"wrote {out} ({len(page)} bytes)")
    return EXIT_OK
