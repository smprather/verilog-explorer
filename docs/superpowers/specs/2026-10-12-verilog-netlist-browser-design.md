# verilog-explorer — design

2026-10-12 · status: draft, awaiting approval · author: Pi + Myles

## 1. Why this exists

A synthesised Verilog netlist is the ground truth about what the tools actually built, and it
is close to unreadable by hand. `rtl/` is behaviour a human wrote; the netlist is 9,983 cells
called `sg13g2_a22oi_1` and nets called `$abc$67326$new_n1627`. Every existing viewer for this
either costs money (Verdi, HDL Designer), ships inside a 20 GB vendor IDE (Vivado, Quartus), or
renders a picture without answering questions (`netlistsvg`, `yosys show`).

This is a small tool for one job: **look at a synthesised design and understand what is in it** —
browse the hierarchy down to leaf cells, see what each module contains, and read that module's RTL
beside it.

It exists because of a specific moment: the design in `~/janestreet-blog-serial-protocol-emulator`
was built by a swarm of agents, the design record is prose, and the first honest look at it starts
with synthesis. Six `.ys` scripts in `reviews/` no longer match the tree — they omit `rtl/pe_ctrl.v`,
which is now the largest block in the design (3,827 cells, bigger than `pe_soc`). File lists are
facts about the past; the netlist is what is there now.

## 2. What day one is

One command, one file:

```console
verilog-explorer top-mapped.json --src-root /path/to/synthesis/cwd -o ve.html
```

- **Input**: a yosys JSON netlist (`write_json`) — day one consumes a **mapped** netlist — and
  optionally the root that the recorded `src` paths are relative to.
- **Output**: one self-contained HTML file, no server, no CDN, no network, opens over `file://`.
- Browsing: hierarchy tree, per-module contents, net inspection, RTL source beside it.
- Everything client-side and static.

## 3. Goals

1. Answer "what is in this design" in one screen: how many modules, how big, where the cells
   actually went, what is unusual.
2. Browse the hierarchy to leaf cells without the names becoming unreadable.
3. Show a module's RTL next to its structure, with honest cross-probing.
4. Report the structural observations a netlist can actually prove — and refuse to claim the rest.
5. Be trustworthy in the specific sense that matters: **never state something the data does not support.**

## 4. Non-goals (day one)

- Not a simulator, waveform viewer, editor, equivalence checker, or timing/area tool.
- No gate-level schematic drawing. See §6.1 — this is a deliberate, evidence-backed decision.
- No server, daemon, database, incremental loading, or live update.
- No support for arbitrary netlist dialects (Vivado/Quartus netlists, RTLIL, CDL). Input is yosys JSON.
- No multi-design diff, no history, no annotations.

## 5. Anti-goals (what would make this a failure even if it works)

- **Rendering a hairball.** If a 3,827-cell module gets drawn as a picture, the tool has failed
  the way the vendor tools fail.
- **Lying about provenance.** A "click to source" that lands on a plausible-but-wrong line is
  worse than no link. 84% of gates carry no source at all and the UI must say so.
- **Crying wolf.** `pe_dru`'s latches are a documented, deliberate two-phase latch. A tool that
  flags them as bugs teaches its user to ignore it.
- **Needing ceremony.** If looking at a netlist requires a running service, it will not be used.
- **Over-generalising early.** Generalising to every vendor netlist before this design is readable
  is how it becomes a project instead of a tool.

## 6. Decisions already made

### 6.1 No gate schematic. (my call, from evidence)

yosys's own documentation says full-module schematics "are just stupidly big and are no help at
all", and `yosys show` is selection-scoped for exactly this reason. Quartus's answer is to bucket
a module's contents by object kind (instances / flops / gates by type / ports / nets) rather than
draw all of it. So the centre pane is a bucketed, filterable table, not a canvas.

**Escape hatch, not day one:** shell out to `yosys show` for a *selected cone* (drivers of a net,
one level deep) if a picture is ever wanted. That is the honest shape of "schematic here".

### 6.2 Input is yosys JSON. (my call)

Richest available data (the only source with `src` ranges and `hide_name`), already produced by the
user's toolchain, and the format is documented in one yosys source file. A generic Verilog-netlist
parser stays behind a seam — `load_netlist()` returning our own model — for a later day.

### 6.3 stdlib only, Python >= 3.14, uv. (user's, from the scaffold)

`pyproject.toml` already declares zero dependencies, src layout, console script
`verilog-explorer`. Nothing in day one needs a library.

### 6.4 Naming: derive readable names, keep the raw key. (my call, from data)

Module keys are `$paramod\pe_ctrl\WORDS=s32'00000000000000000000010000000000`; yosys already gives
`attributes.hdlname` = `pe_ctrl` on every derived module (observed on 11/11 in two specimens).
Fallback for keys without it: strip `^\$paramod(\$[0-9a-f]{40})?\\([^\\]+)`. Show the readable name
as the label, hang the parameter off as a badge, keep the full key available — never as the label.

### 6.5 Flavour: mapped first, and the page says which. (my call, from reviewer finding #1)

Day one consumes a mapped netlist and says so. The flavour is **derived from the data** — which cell
types appear (`sg13g2_*` mapped leaves vs `$adff`/`$dlatch` operators) — and printed in the header,
never typed in. The RTL-ish dump stays out of day one: it is a different cell vocabulary, and the
two-flavour toggle is the natural next step (open question 2 in §15).

Consequence for honesty: a negative result may only be printed if the loaded flavour can compute
it. "0 width truncation" needs width metadata that a mapped netlist does not carry, so on day one
the page does not print it.

### 6.6 Sequential cells are classified, not listed. (my call, from reviewer finding #5)

No hand-typed type table (rule 6). A cell is sequential if its port signature says so: a flop has a
clock-like port plus a data input and a data output; a latch has data in and out with a gate/enable
and no clock. A short name table (`dfrbp`, `dlhq`, `$dff`, `$dlatch`) is a documented fallback only,
and a test proves the signature classifier on a synthetic netlist.

### 6.7 Source resolution, drift, and exit codes. (my call, from reviewer findings #3 and #4)

- **Path rule.** `src` values are relative to the directory synthesis ran in, so the flag is
  `--src-root DIR` (the synthesis cwd, *not* the RTL directory) and a source resolves as
  `DIR / src_path`, exactly. No basename matching and no searching across roots: a
  plausible-but-wrong link is the anti-goal in §5.
- **Missing file.** Stated in the source pane. Not an error — a netlist is readable without its RTL.
  A `--src-root` that resolves nothing at all is exit 2.
- **Stale file.** If a `src` range ends past the end of the file on disk, the pane says the file is
  not the revision the netlist was built from. That is the cheapest honest drift check, and drift is
  the exact failure this tool exists to prevent (`FINDINGS.md` §5). Anything deeper is out of scope
  and says so.
- **Exit codes.** `0` = rendered, and findings are *content*, never an error. `1` = `--check` found
  the page stale. `2` = cannot complete. Findings must not change the exit code, or a gate cannot
  tell "the page is stale" from "the design has latches".

## 7. Measured facts the design rests on

From `recon/01-synth/top-mapped.json` (the whole `tt_um_protocol_emulator`, hierarchy intact,
sg13g2 leaves) — every number reproducible via `recon/01-synth/measure.py`:

|   |   |
| --- | ---: |
| design modules / library stubs | 16 / 85 |
| submodule instances / leaf cells | 18 / 9,965 |
| flops / latches | 1,714 / 2 |
| distinct cell types | 44 |
| max hierarchy depth | 4 |
| JSON size | 6.5 MB |

Largest blocks: `pe_ctrl` 3,827 · `pe_soc` 2,059 · `pe_eth_mac` 1,642 · `pe_eth_tx` 850 ·
`pe_serdes` 534.

Cross-probe budget — `src` survives on **100% of submodule instances, 92% of flops, 0% of
combinational gates** (abc re-synthesises and discards it). A flop's `src` is a *range*:
`rtl/pe_ctrl.v:636.3-1326.6` is a 690-line `always` block, not a statement.

These figures are for the mapped flavour, and the flop/latch counts come from the classifier in
§6.6 rather than from a type table.

## 8. Data model notes (the traps, all observed)

- **Bits, not names.** Every connection is a list of integer indices into a module-local bit pool,
  plus the constants `"0" "1" "x" "z"`. A bit may have **many** names, and one netname may repeat a
  bit (`pe_fbuf.g_macro.bm_m = [52 ×8, 51 ×8]`). Never build a 1:1 bit↔name map.
- **Vectors are unsorted and LSB-first by position**: `dbg_pc = [39,42,14,15,16,17,80,81,82,83]`.
  Do not sort; do not assume `len(bits) == width`.
- **"Is this driven?" is a bit question.** A port can alias a module *input* or an internal net and
  have no driving cell at all (`pe_cpu.io_port` = `imem_rdata` bits 17-20). Union all names per bit;
  count module input-port bits as sources. Ignoring `port_directions` produced 160 false positives
  in our own first attempt.
- **Stubs are modules too.** `read_liberty -lib` emits a stub module per library cell, so
  `type in modules` is true for every stdcell. A leaf is a type whose module has no cells.
- **Attribute booleans are 32-bit binary strings**, not `true`/`1`.
- **`write_json` refuses a module containing processes** ("run `proc` first"), so the RTL-ish dump
  must be taken after `proc`.

## 9. The page

Three panes, one screen, no navigation to speak of:

**Header** — design stats: modules, cells, flops, latches, depth, plus the **derived flavour**
(§6.5). Every one of these is computed from the loaded netlist.

**Left, hierarchy** — the instance tree, labelled with `hdlname`, counts per node, and badges:
`WORDS=1024` for parameters, `2 latches`, `SRAM`. Auto-reveal the selection; toggleable.
Flags must be *facts*, never alarms.

**Centre, contents of the selected module** — bucketed by kind, à la Quartus Netlist Navigator:
- instances (name, module, fanout)
- flops (`sg13g2_dfrbpq_1` and friends) — with the readable name derived from the **Q net**
- gates grouped by cell type, with counts and a bar per type
- ports (direction, bits, aliases)
- nets: driver and load lists as text — Verdi's nTrace view, which needs no picture
Plus the per-module observations from §10, phrased as observations.

**Right, RTL source** — the module's file, scrolled to the selection's `src` range; absent source is
stated in words. Follows the selection, with a pin toggle.

**Cross-cutting** — filter/search by name, type, or flag; every view shares one selection.

## 10. What to detect, and how to phrase it

Five detections are worth showing, measured by `recon/05-anomalies/probe.py`:

| observation | method | measured here |
| --- | --- | --- |
| Inferred latch cells | cell type is a latch (`sg13g2_dlhq_1`, `$dlatch`) | 2, both `pe_dru`, deliberate (pe_dru.v:185,188) |
| Register files that look like memory | group array-indexed netnames, test flop-Q dominance | 4: `dmem` 128b, `win_regs` 198b, `resp_buf` 256b, `fifo_mem` 64b |
| Dead named nets | every bit of a named net has zero loads | 20, incl. `crc_state[31:0]`, `consume_credit[10:0]` |
| Constant-driven named signals | all bits constant, after filtering `_unused*`/`$func$`/hidden | 2 normal signals of 85 raw |
| Blackbox macro instances | non-library module with no cells | 2 SRAM macros; do not expand these |

Rules for presenting them:
- **Two classes**: structural facts that are always wrong (multiple drivers) vs observations whose
  bug-ness lives in the RTL. Day one shows the second class *as observations with an RTL pointer*.
- **Filter before crying wolf.** 85 constant nets is noise; 2 named signals is the finding. 20 dead
  nets are mostly debug taps. A detection that cannot survive a filter is not shipped.
- **Negative results are results — but only the ones this flavour can compute.** On a mapped
  netlist: no multiple drivers, no undriven output, no undriven port. Width truncation needs the
  RTL-ish dump, so it is not claimed. A negative printed without the check behind it is the same
  lie as a positive one.
- **Label structure, not intent.** "register file (inferred)", never "RAM".

## 11. House rules to follow

Adopted from the conventions of `janestreet-blog-serial-protocol-emulator` (see
`recon/04-house-style/HOUSE-STYLE.md`), because this tool will be read by the same person:

1. Module docstring stating **why it exists** and the failure that motivated it — not what it does.
2. argparse with `description=__doc__`; long lowercase hyphenated flags; `-o` for the output file.
3. Exit codes: `0` clean, `1` findings, `2` cannot complete (missing input). Never fail open, never
   silently skip a missing dependency.
4. The artifact is a file, not stdout; stdout says `wrote <path> (n bytes)`.
5. stdlib only, no network at run time.
6. Derive everything from the inputs; never carry a hand-typed table that can drift from the netlist.
7. A guard that cannot fail is not a guard — the tests must be able to fail (see §13).
8. `--check` re-renders in memory and compares, so the repo can gate the output later if it wants.

## 12. Left to the builder

- Module layout under `src/verilog_explorer/`: `load.py` (JSON → model), `naming.py` (labels, bits),
  `nets.py` (driver/load index on bit indices), `classify.py` (flop/latch classification by port
  signature, §6.6), `detect.py` (the five observations), `render.py` (HTML), `cli.py`.
- The one-hop boundary hint in the net pane: for a net whose driver is a module input, name the
  parent instance port that feeds it (`fed by u_soc.imem_addr`). The tree already knows the
  parent/child relation, so this is cheap; full hierarchical tracing is not (open question 3, §15).
- The reduced model embedded in the page — target well under the 6.5 MB input; measure and say what
  it weighs.
- HTML/CSS/JS: no framework, no build step. Tree, panes, filters, one selection.
- The `--check` mode and a test that **fails** against a mutated netlist (e.g. flip one cell's
  `port_directions` and assert the driver/load counts change).
- Decide and document: how much of the net is embedded vs recomputed client-side.
- Day two, in order: (a) a `dump` mode that runs the known-good yosys recipe (`recon/01-synth/dump-top.ys`)
  so the user does not hand-write `.ys` files; (b) the `yosys show` selected-cone picture;
  (c) the RTL-ish dump (operators visible) as a second view of the same instance.

## 13. How we will know it works

- `verilog-explorer recon/01-synth/top-mapped.json --src-root /home/mylesp/janestreet-blog-serial-protocol-emulator -o /tmp/ve.html`
  produces a file that opens, and the header numbers match `recon/01-synth/REPORT.md`. Note that
  `recon/` is gitignored scratch, so this is a **local smoke check**, not a committed test.
- Selecting `pe_ctrl` shows 3,827 cells, 625 flops, and a type histogram matching the report.
- Selecting the `sg13g2_dlhq_1` cells in `pe_dru` lands on `rtl/pe_dru.v:185`, and **says** that the
  source is a range.
- Selecting a combinational gate says it has no source, rather than guessing.
- The test suite has at least one test that fails when a netlist fact is mutated.

**Fixtures.** The committed corpus is small, synthetic, and owned by this repo: a handful of
hand-written designs (a parameterised submodule, a flop, a latch, a constant tie, a dead net, an
aliased port) with their dumps committed beside the test. Assertions that need the real 6.5 MB recon
dump run only when that file is present, and report **INCOMPLETE (exit 2)** when it is not — never a
silent pass. Making a scratch artifact a precondition of the tests that verify it is how a guard
stops being able to fail.

## 15. Open — the day-one boundary

Three edges are not settled by this document, and they are the user's to move:

1. **A drawn schematic instead of the bucketed table.** Needs a layout engine and a different plan
   (§6.1). Recommendation: no.
2. **Both netlist flavours in day one** (mapped + RTL-ish, with a toggle) instead of mapped only. The
   RTL-ish dump already exists in recon, and it is the other half of the structure-vs-behaviour idea
   this tool started from. Recommendation: mapped first, toggle next.
3. **Hierarchical net tracing** (follow a net through instance ports into the parent) instead of
   module-local driver/load lists. Recommendation: module-local plus the one-hop hint in §12.

Everything else in this document is decided.

## 14. Evidence

| claim | where |
| --- | --- |
| measurements, cross-probe budget, naming | `recon/01-synth/FINDINGS.md`, `REPORT.md`, `measure.py`, `dump-top.ys` |
| yosys JSON schema, `hdlname`, bit semantics, the three gotchas | `recon/02-json-schema/SCHEMA.md` |
| viewer conventions, the yosys "no help at all" quote, licences | `recon/03-prior-art/PRIOR-ART.md` |
| house style and the ten rules | `recon/04-house-style/HOUSE-STYLE.md` |
| the five detections, 14-row table, negative results | `recon/05-anomalies/DETECTABLE.md` |
| the day-one page with real data in it | `.superpowers/brainstorm/*/content/day-one-page.html` |
