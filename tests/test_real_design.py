"""The acceptance run against the real design.

Not a unit test, and it cannot become one: `recon/` is gitignored scratch holding the
6.5 MB dump this whole project was measured against, so there is nothing to commit as
a fixture. It therefore reports **INCOMPLETE** rather than skipping.

That distinction is the point. A test that is not there is indistinguishable from a
test that passed, and this is the one that pins the numbers the design document quotes —
`pe_ctrl` at 3,827 cells and 625 flops, and the two `pe_dru` latches landing on the RTL.
If someone changes the model so those numbers move without noticing, this fails loudly
and says what changed.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from verilog_explorer.cli import main

REPO = Path(__file__).resolve().parents[1]
RECON = REPO / "recon" / "01-synth"
NETLIST = RECON / "top-mapped.json"
SRC_ROOT = Path.home() / "janestreet-blog-serial-protocol-emulator"

MODEL_BLOCK = re.compile(
    r'<script id="ve-model" type="application/json">(?P<body>.*?)</script>', re.DOTALL
)

# The register files the reference design's RTL calls arrays and synthesis built out of
# flops, with the bit widths measured by the recon pass.
REGISTER_FILES = {"dmem", "win_regs", "resp_buf", "fifo_mem"}


def _render(tmp_path: Path) -> tuple[int, Path]:
    out = tmp_path / "ve.html"
    code = main(
        [
            str(NETLIST),
            "-o",
            str(out),
            "--src-root",
            str(SRC_ROOT),
        ]
    )
    return code, out


def test_the_reference_design_renders(tmp_path, capsys):
    code, out = _render(tmp_path)
    captured = capsys.readouterr()

    if not (NETLIST.exists() and SRC_ROOT.exists()):
        assert code == 2, (
            f"expected exit 2 (cannot complete) without the recon dump, got {code}. "
            "INCOMPLETE is not SKIP: say so out loud."
        )
        assert NETLIST.name in captured.err or "cannot read" in captured.err, captured.err
        return

    assert code == 0, captured.err
    assert out.is_file()

    started = time.perf_counter()
    code, out = _render(tmp_path)
    elapsed = time.perf_counter() - started
    captured = capsys.readouterr()

    page = out.read_text(encoding="utf-8")
    match = MODEL_BLOCK.search(page)
    assert match is not None, "the page has no embedded model"
    model = json.loads(match.group("body"))

    assert model["flavour"] == "mapped"
    by_label = {m["label"]: m for m in model["modules"]}

    # These two numbers are the ones the design document quotes. If they move without
    # the document moving, the document is now wrong.
    ctrl = by_label["pe_ctrl"]
    assert ctrl["cells"] == 3827, f"pe_ctrl cells {ctrl['cells']}, document says 3827"
    assert ctrl["flops"] == 625, f"pe_ctrl flops {ctrl['flops']}, document says 625"

    latches = [f for f in model["findings"] if f["code"] == "latch"]
    assert len(latches) == 2, f"expected the two pe_dru latches, got {len(latches)}"
    for finding in latches:
        assert "pe_dru.v" in (finding["where"] or ""), finding

    found = {f["subject"].split(".")[-1] for f in model["findings"] if f["code"] == "register-file"}
    assert REGISTER_FILES <= found, f"missing register files: {sorted(REGISTER_FILES - found)}"

    assert any("no multiple drivers" in line for line in model["negatives"])
    assert not any("width truncation" in line for line in model["negatives"])

    # Both halves of the performance question, stated rather than assumed.
    assert elapsed < 10.0, f"rendering took {elapsed:.1f}s"
    assert len(page) < 2_000_000, f"page is {len(page)} bytes"
    print(
        f"\nreference design: {NETLIST.stat().st_size / 1e6:.1f} MB netlist -> "
        f"{len(page) / 1e3:.0f} KB page in {elapsed:.2f}s"
    )
