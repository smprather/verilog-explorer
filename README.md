# verilog-explorer

Read a synthesised Verilog netlist and render it for browsing.

One command, one file, no server:

```bash
verilog-explorer top-mapped.json --src-root ~/janestreet-blog-serial-protocol-emulator -o ve.html
```

## Why this exists

The netlist is the ground truth about what the tools actually built, and it is close to
unreadable by hand. `rtl/` is behaviour a person wrote; the mapped netlist is 9,965
cells called `sg13g2_a22oi_1` and nets called `$abc$67326$new_n1627`. Every existing
viewer either costs money, ships inside a large vendor IDE, or draws a picture without
answering questions.

This came out of wanting to actually *look* at a design a swarm of agents had built and
to answer, in one place: how big is each block, what did synthesis do that the RTL does
not say (latches inferred, arrays that became register files, dead nets), and can I read
the RTL beside the structure it became.

## What it does not do

- No gate-level schematic. yosys's own documentation calls full-module schematics "just
  stupidly big and are no help at all". The page buckets a module's contents by kind
  instead, and `yosys show` on a *selected* cone is the escape hatch when a picture is
  wanted.
- No server, database, or install: the output is one self-contained HTML file that opens
  from `file://`, with nothing fetched from anywhere.
- No simulator, waveform viewer, editor, or equivalence checker.
- Input is yosys JSON only. A mapped netlist on day one; the RTL-ish flavour from the
  same flow is the next view.

## Honesty rules the page follows

- Labels come from `attributes.hdlname`, never from a `$paramod…` key. Parameters become
  a badge (`WORDS=1024`), not part of the name.
- Click-to-source is real where yosys kept the attribution — 100% of submodule instances
  and 92% of flops — and **absent on combinational gates**, where abc discarded it. A gate
  with no source says so.
- A `src` range that runs past the end of the file on disk is reported as drift, because
  a source pane scrolled to a stale range is the failure this tool exists to prevent.
- Findings are observations, not accusations. `pe_dru`'s latches are a documented
  two-phase latch; the page shows them and defers to the RTL.
- A negative result is only printed if the loaded flavour can compute it. A mapped netlist
  carries no width metadata, so "no width truncation" is never claimed.

## Exit codes

| code | meaning |
| --- | --- |
| `0` | rendered — findings are content and never change this |
| `1` | `--check` found the file on disk does not match the netlist |
| `2` | cannot complete: unreadable input, or a `--src-root` that resolves nothing |

## Input

`write_json` from yosys, taken **before** `flatten` so the module hierarchy survives:

```bash
read_liberty -lib <your liberty>
read_verilog -sv rtl/*.v rtl/vendor/<macro>.bb.v
hierarchy -check -top <your top>
proc; opt; fsm; opt; memory; opt
write_json mapped.json       # hierarchy intact, leaf cells are real library cells
```

`dump-top.ys` in the recon notes has the working invocation for the reference design.

## Development

```bash
uv sync --dev
uv run pytest tests/ -q       # 94 tests; the real-design one reports INCOMPLETE
uv run verilog-explorer <netlist.json> -o /tmp/ve.html
```

`recon/` holds the measurements, the yosys JSON schema reference, a prior-art survey,
the house-style rules the code follows, and the detectability table. The design and its
plan are in `docs/superpowers/`.
