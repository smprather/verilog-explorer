# verilog-explorer day one — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One command turns a yosys JSON netlist into a single self-contained HTML page that lets you browse a synthesised design's hierarchy, the contents of each module, its nets, and the RTL beside it.

**Architecture:** A pure-stdlib Python package loads the netlist into a small in-memory model, derives hierarchy/tree and net indices from it, and renders one HTML file with the reduced model embedded as JSON and a vanilla-JS viewer. Hierarchy is always *inferred* by `hierarchy.py` from the model — today from module-instance cells, later from `/`-separated instance-name paths — so a flat million-gate netlist is a second strategy, not a rewrite.

**Tech Stack:** Python >= 3.14, stdlib only at runtime (`argparse`, `json`, `pathlib`, `re`, `html`, `dataclasses`), pytest as the only dev dependency, uv for env and build, no JS dependencies, no build step.

**Spec:** `docs/superpowers/specs/2026-10-12-verilog-netlist-browser-design.md`

## Global Constraints

- Python `>= 3.14`; runtime deps stay empty. Tests may use pytest.
- Exit codes: `0` rendered, `1` `--check` found the page stale, `2` cannot complete. Findings are content and never change the exit code. Never fail open; never silently skip a missing input.
- Module labels come from `attributes.hdlname`, falling back to stripping `^\$paramod(\$[0-9a-f]{40})?\\([^\\]+)`. The raw key is never the label.
- A bit is a string: `"12"` is a module-local bit index, `"0" "1" "x" "z"` are constants. Bit tuples are **unsorted and LSB-first by position** — never reorder them, never assume `len(bits) == width`.
- A bit may have many names and a name may repeat a bit. Never build a 1:1 bit↔name map.
- Stubs are modules too: a type is a leaf iff its module has no cells of its own.
- "Is this driven?" is answered on bit indices: sources are cell output/inout bits ∪ module input-port bits ∪ constants; module output-port bits count as loads.
- No gate-level schematic, no layout engine, no canvas.
- Negative results print only if the loaded flavour can compute them. On a mapped netlist: no multiple drivers, no undriven output, no undriven port. Width truncation is not claimed.
- `src` values resolve as `src_root / src_path` exactly — no basename matching, no searching across roots.

## Review Focus

Failure modes the spec implies and no single task's tests would otherwise cover. Each is pinned to a test in the task that owns the code.

1. **A module key with no `hdlname`** — must fall back to the regex strip, not display `$paramod\…` (Task 2).
2. **A malformed or unusable `src`** — `rtl/x.v:10.1-2.3`, a file that does not exist, or a `src` with no `:` — must degrade to "no source"/"not the revision", never a traceback (Tasks 6, 8).
3. **Input that is not a netlist** — a JSON document without `modules`, or a missing file — must exit 2 with a sentence, never a traceback (Task 8).
4. **The real 6.5 MB dump** — build time and embedded size stay usable, and derived indices are computed per selected module rather than eagerly for all 16 (Task 9).
5. **A net whose bits are all constants** — must never be counted as driving a module input port (Tasks 4, 5).

---

## File structure

| file | responsibility |
|---|---|
| `src/verilog_explorer/model.py` | dataclasses for `Design`, `Module`, `Cell`, `Port`, `Net`; `is_const`, `is_stub` |
| `src/verilog_explorer/load.py` | yosys JSON → `Design`; flavour detection |
| `src/verilog_explorer/hierarchy.py` | the one place hierarchy is inferred; module-structure strategy today |
| `src/verilog_explorer/naming.py` | module labels, parameter badges, bit/vector formatting, net display names |
| `src/verilog_explorer/classify.py` | port-signature classification: instance / flop / latch / gate / macro |
| `src/verilog_explorer/nets.py` | per-module bit-index driver/load index; one-hop parent hint |
| `src/verilog_explorer/detect.py` | the five observations and the per-flavour negative results |
| `src/verilog_explorer/source.py` | `src` range parsing, resolution against `--src-root`, drift check |
| `src/verilog_explorer/assets.py` | the viewer's CSS and JS as string constants |
| `src/verilog_explorer/render.py` | `Design` → one self-contained HTML string |
| `src/verilog_explorer/cli.py` | argparse, exit codes, `--check` |
| `src/verilog_explorer/__init__.py` | re-export `main` for the console script |
| `tests/fixtures/` | synthetic designs + their yosys dumps, committed |

---

### Task 1: Model and loader

**Files:**
- Create: `src/verilog_explorer/model.py`, `src/verilog_explorer/load.py`
- Test: `tests/test_load.py`

**Interfaces:**
- Produces: `Cell(name, type, src, connections, port_directions, parameters)`, `Port(name, direction, bits, signed)`, `Net(name, bits, hide_name)`, `Module(name, hdlname, cells, ports, netnames, is_stub)`, `Design(modules, flavour, top, source_path)`, `is_const(bit: str) -> bool`, `load_design(path: Path) -> Design`, `detect_flavour(design: Design) -> str` returning `"mapped" | "rtl-ish" | "unknown"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_load.py
from verilog_explorer.load import load_design
from verilog_explorer.model import is_const

NETLIST = {
    "creator": "Yosys 0.69",
    "modules": {
        "top": {
            "attributes": {"top": "00000000000000000000000000000001"},
            "ports": {
                "a": {"direction": "input", "bits": [2]},
                "y": {"direction": "output", "bits": [3]},
            },
            "cells": {
                "u_sub": {
                    "hide_name": 0,
                    "type": "sub",
                    "port_directions": {"a": "input", "y": "output"},
                    "connections": {"a": ["2"], "y": ["3"]},
                    "parameters": {},
                    "attributes": {"src": "t.v:3.1-3.9"},
                }
            },
            "netnames": {"a": {"hide_name": 0, "bits": [2]}},
        },
        "sub": {
            "attributes": {"hdlname": "sub"},
            "ports": {"a": {"direction": "input", "bits": [0]}},
            "cells": {},
            "netnames": {},
        },
        "sg13g2_nand2_1": {
            "attributes": {},
            "ports": {"A": {"direction": "input", "bits": [0]}},
            "cells": {},
            "netnames": {},
        },
        "RM_IHPSG13_1P_1024x16_c2_bm_bist": {
            "attributes": {"blackbox": "00"},
            "ports": {},
            "cells": {},
            "netnames": {},
        },
    },
}


def test_stub_is_a_module_with_no_cells(tmp_path):
    p = tmp_path / "n.json"
    p.write_text(json.dumps(NETLIST))
    d = load_design(p)
    assert d.modules["top"].is_stub is False
    assert d.modules["sg13g2_nand2_1"].is_stub is True
    assert d.modules["sub"].is_stub is True


def test_bits_stay_strings_and_keep_order(tmp_path):
    p = tmp_path / "n.json"
    p.write_text(json.dumps(NETLIST))
    d = load_design(p)
    assert d.modules["top"].cells["u_sub"].connections["a"] == ("2",)


def test_constants_are_recognised():
    assert is_const("0") and is_const("x") and not is_const("12")


def test_flavour_is_mapped_when_sg13g2_cells_appear(tmp_path):
    p = tmp_path / "n.json"
    p.write_text(json.dumps(NETLIST))
    assert load_design(p).flavour == "mapped"
```

- [ ] **Step 2: Run test to verify it fails** — `uv run pytest tests/test_load.py -q` → FAIL, `ModuleNotFoundError: verilog_explorer.load`.

- [ ] **Step 3: Implement `model.py` then `load.py`.** Frozen dataclasses; `load_design` reads JSON, converts every connection/bits list to a tuple of `str(bit)`, sets `is_stub = not cells`, `hdlname` from `attributes.hdlname` (or `None`), and `top` from the module carrying the `top` attribute. Flavour: `"mapped"` if any cell type starts with `sg13g2_` or `RM_`; `"rtl-ish"` if any starts with `$`; else `"unknown"`.

- [ ] **Step 4: Run test to verify it passes** — `uv run pytest tests/test_load.py -q` → 4 passed.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: yosys JSON netlist model and loader"`

---

### Task 2: Naming

**Files:**
- Create: `src/verilog_explorer/naming.py`
- Test: `tests/test_naming.py`

**Interfaces:**
- Consumes: `Module`, `Net` from Task 1.
- Produces: `module_label(module: Module) -> str`, `parameter_badges(module: Module) -> list[str]`, `decode_param(value: str) -> str`, `is_auto_name(name: str) -> bool`, `format_bits(bits: tuple[str, ...]) -> str`, `net_label(module: Module, bit: str) -> str`.

- [ ] **Step 1: Write the failing test**

```python
def test_module_label_prefers_hdlname():
    m = mod(
        name="$paramod\\pe_ctrl\\WORDS=s32'00000000000000000000010000000000",
        hdlname="pe_ctrl",
        cells={},
    )
    assert module_label(m) == "pe_ctrl"


def test_module_label_falls_back_to_strip_without_hdlname():
    m = mod(
        name="$paramod$7f9518eacb819f12609a81d25055eeb8d348b0ad\\pe_soc", hdlname=None, cells={}
    )
    assert module_label(m) == "pe_soc"


def test_parameter_badge_decodes_a_binary_s32():
    m = mod(
        name="$paramod\\pe_ctrl\\WORDS=s32'00000000000000000000010000000000",
        hdlname="pe_ctrl",
        cells={},
    )
    assert parameter_badges(m) == ["WORDS=1024"]


def test_bits_render_as_a_range_only_when_contiguous():
    assert format_bits(("0", "1", "2", "3")) == "3:0"
    assert format_bits(("39", "42", "14", "15", "16", "17", "80", "81", "82", "83")) == "10 bits"


def test_auto_names_are_detected():
    assert is_auto_name("$abc$67326$new_n1627")
    assert is_auto_name("$auto$ff.cc:337:slice$28794")
    assert not is_auto_name("resp_buf")


def test_net_label_prefers_the_human_name_for_a_bit():
    m = mod(
        name="pe_ctrl",
        hdlname="pe_ctrl",
        cells={},
        netnames={"clk": ("7",), "$abc$1$new_n5": ("7",)},
    )
    assert net_label(m, "7") == "clk"
```

- [ ] **Step 2: Run test to verify it fails** — `uv run pytest tests/test_naming.py -q` → ImportError.

- [ ] **Step 3: Implement.** `decode_param` turns yosys's `s32'000…100` into `1024` (strip the `sN'`/`uN'` prefix, parse base 2, keep the raw form when it will not parse); `format_bits` sorts a *copy* for the contiguity test only; `net_label` picks the shortest non-hidden name that is not an auto-name, else the shortest name, else `bit N`.

- [ ] **Step 4: Run test to verify it passes** — 6 passed.

- [ ] **Step 5: Commit** — `git commit -am "feat: readable names, parameter badges, bit formatting"`

---

### Task 3: Hierarchy

**Files:** Create `src/verilog_explorer/hierarchy.py`; Test `tests/test_hierarchy.py`

**Interfaces:**
- Consumes: `Design`.
- Produces: `Node(path: str, label: str, module: str, children: tuple[Node, ...])`, `build_tree(design: Design) -> Node`, `module_cells(design, module_name) -> int`.

- [ ] **Step 1: Write the failing test** — build a three-level fixture (`top` → `u_sub` → `u_leaf`); assert `build_tree(d).path == "top"`, `[c.label for c in tree.children] == ["u_sub"]`, `tree.children[0].children[0].module == "leaf"`, and that a module instantiated twice produces two nodes with distinct paths.
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement** by walking instance cells (a cell whose type is a non-stub module). This is the single seam: a second strategy reading `/`-separated instance names is added here later, and nothing else changes.
- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit.**

---

### Task 4: Cell classification

**Files:** Create `src/verilog_explorer/classify.py`; Test `tests/test_classify.py`

**Interfaces:**
- Produces: `cell_kind(cell: Cell, design: Design) -> str` in `{"instance", "flop", "latch", "gate", "macro"}`.

- [ ] **Step 1: Write the failing test** — using yosys-shaped synthetic cells, assert: `sg13g2_dfrbpq_1` with ports `{CLK,D,Q,RESET_B}` → `"flop"`; `sg13g2_dlhq_1` with `{D,G,Q}` → `"latch"`; `$dff` with `{CLK,D,Q}` → `"flop"`; `$dlatch` with `{EN,D,Q}` → `"latch"`; `sg13g2_nand2_1` → `"gate"`; `RM_IHPSG13_…` → `"macro"`; a cell typed as a non-stub module → `"instance"`.
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement** the port signature: clock-like ports `{"CLK","C","CK"}`, gate-like `{"G","EN","E"}`, data `D` and `Q`. Flop = clock ∧ D ∧ Q; latch = gate ∧ D ∧ Q ∧ no clock; no name table is consulted except as a fallback when a type's ports are missing entirely.
- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit.**

---

### Task 5: Net index

**Files:** Create `src/verilog_explorer/nets.py`; Test `tests/test_nets.py`

**Interfaces:**
- Produces: `NetIndex` with `drivers(bit) -> tuple[Cell, ...]`, `loads(bit) -> tuple[Cell, ...]`, `boundary(bit) -> str | None` (`"const"`, or `"port:<name>"` when the module's own input port owns that bit`), `dead_nets() -> tuple[Net, ...]`, `parent_hint(design: Design, module: str, port: str) -> str | None`.

- [ ] **Step 1: Write the failing test** — including the regression that produced 160 false positives:

```python
def test_a_port_that_aliases_a_module_input_is_not_undriven():
    # pe_cpu.io_port is assign io_port = arg[3:0]; its bits are the input port's bits,
    # and no cell drives them.
    m = mod_with(cells={}, ports={"arg": {"input": ["17", "18", "19", "20"]},
                                 "io_port": {"output": ["17", "18", "19", "20"]}})
    ix = NetIndex(m, design={})
    assert ix.boundary("17") == "port:arg"


def test_a_load_is_a_cell_input_port_on_that_bit():
    ...assert ix.loads("7") == (cell,)


def test_constant_bits_are_driven_by_definition():
    ...assert ix.boundary("0") == "const"


def test_parent_hint_names_the_instance_port():
    ...assert ix.parent_hint(design, "pe_soc", "imem_addr") == "u_soc.imem_addr"
```

- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement.** One pass per module building `bit → [cells]` for inputs and outputs; module input-port bits and constants count as sources; module output-port bits count as loads for `dead_nets`.
- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit.**

---

### Task 6: Source resolution and drift

**Files:** Create `src/verilog_explorer/source.py`; Test `tests/test_source.py`

**Interfaces:**
- Produces: `SRC_RE`, `parse_src(value: str) -> tuple[str, int, int] | None`, `SourceIndex(src_root: Path | None)` with `.locate(src) -> tuple[Path, int, int] | None`, `.lines(path) -> list[str] | None` (cached), `.drift(src) -> str | None`.

- [ ] **Step 1: Write the failing test** — `parse_src("rtl/pe_ctrl.v:636.3-1326.6") == ("rtl/pe_ctrl.v", 636, 1326)`; `parse_src("nonsense") is None`; a range whose end exceeds the file's line count yields a drift sentence containing "not the revision"; a missing file yields `None` from `locate`, not an exception; `SourceIndex(None)` never raises.
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement.** `src_root / src_path` exactly, no basename fallback.
- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit.**

---

### Task 7: Detections

**Files:** Create `src/verilog_explorer/detect.py`; Test `tests/test_detect.py`

**Interfaces:**
- Consumes: `Design`, `NetIndex`, `cell_kind`.
- Produces: `Finding(code, subject, detail, klass, where)`, `detect(design, *, per_module=None) -> list[Finding]`, `negative_results(design) -> list[str]`.

- [ ] **Step 1: Write the failing test** — one fixture per observation: a latch cell yields a `latch` finding; a named net with all bits unloaded yields `dead-net`; a constant net named `_unused_gate` must **not** be reported while `host_imem_sel` must; a blackbox macro yields `macro`; a group of flops whose `Q` nets share an array prefix yields `register-file`. Assert `negative_results(mapped)` contains "multiple drivers" and does **not** contain "width truncation".
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement.** Each finding carries `klass` = `"observation"` (its bug-ness lives in the RTL) — no `"error"` class exists yet, because nothing in day one is provably wrong. Filters: drop names matching `^_unused`, `^\$func\$`, hidden names, and `$`-locals before reporting constants.
- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit.**

---

### Task 8: Renderer and CLI

**Files:** Create `src/verilog_explorer/assets.py`, `render.py`, `cli.py`; modify `__init__.py`; Test `tests/test_render.py`, `tests/test_cli.py`

**Interfaces:**
- Produces: `render_html(design, tree, findings, sources, *, title) -> str`, `main(argv=None) -> int`.

- [ ] **Step 1: Write the failing tests** — `render_html` output contains the top module label, the cell count, and `<script id="model" type="application/json">`; `main(["--help"])` exits 0; `main([str(fixture), "-o", str(out)])` writes a file and exits 0; `main([str(fixture), "-o", str(out), "--check"])` exits 1 after the file is edited and 0 when unchanged; `main([str(tmp/"not-a-netlist.json"), "-o", x])` exits 2 and prints a sentence (no traceback); `main([...,"--src-root", str(missing)])` with a netlist whose sources do not resolve exits 2.
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement** the CLI (`argparse` with `description=__doc__`, flags `-o/--out`, `--src-root`, `--check`, `--title`) and the renderer: three panes, header stats from the model, the tree, the selected module's bucketed contents, findings, and the source pane; the model embedded as JSON; `--check` compares bytes and prints `stale`/`ok`.
- [ ] **Step 4: Run to verify it passes.**
- [ ] **Step 5: Commit.**

---

### Task 9: Real-design acceptance and repo hygiene

**Files:** Create `tests/test_real_design.py`, modify `README.md`

- [ ] **Step 1: Write the local-only acceptance test** — skip-free: if `recon/01-synth/top-mapped.json` is absent, the test **fails with the INCOMPLETE marker** (exit code 2 from the CLI, message naming the missing path); if present, it renders and asserts `pe_ctrl` shows 3,827 cells and 625 flops, and that a `sg13g2_dlhq_1` cell's source lands in `pe_dru.v`. Measure and print the build time and the HTML size.
- [ ] **Step 2: Run against the real dump** — `time uv run verilog-explorer recon/01-synth/top-mapped.json --src-root ~/janestreet-blog-serial-protocol-emulator -o /tmp/ve.html`, then open it.
- [ ] **Step 3: Fix whatever the real data breaks.** Expect at least one: parameter badges, unsorted vectors, `$abc$` names, 6.5 MB parse time.
- [ ] **Step 4: README** — the why-docstring in prose, the command, what it does not do.
- [ ] **Step 5: Commit and push** — `git push -u origin master`.
