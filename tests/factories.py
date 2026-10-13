"""Factories for building netlist models in tests without running yosys.

Tasks 2-7 all need a `Module` with a couple of cells and nets in it. Building one
by hand in every test buried the assertion under the setup, so the shapes live here.

Bit arguments follow the format: pass an **int** for a bit index and a **str** for
a constant.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from verilog_explorer.model import Bit, Cell, Design, Module, Net, Port


def make_cell(
    name: str = "u0",
    type: str = "sg13g2_nand2_1",
    src: str | None = None,
    connections: Mapping[str, Iterable[Bit]] | None = None,
    port_directions: Mapping[str, str] | None = None,
    parameters: Mapping[str, str] | None = None,
) -> Cell:
    return Cell(
        name=name,
        type=type,
        src=src,
        connections={k: tuple(v) for k, v in (connections or {}).items()},
        port_directions=dict(port_directions or {}),
        parameters=dict(parameters or {}),
    )


def make_port(
    name: str, direction: str = "input", bits: Iterable[Bit] = (), signed: bool = False
) -> Port:
    return Port(name=name, direction=direction, bits=tuple(bits), signed=signed)


def make_net(name: str, bits: Iterable[Bit] = (), hide_name: bool = False) -> Net:
    return Net(name=name, bits=tuple(bits), hide_name=hide_name)


def make_module(
    name: str = "m",
    hdlname: str | None = None,
    cells: Mapping[str, Cell] | None = None,
    ports: Mapping[str, Port] | None = None,
    netnames: Mapping[str, Net] | None = None,
    is_stub: bool | None = None,
    is_top: bool = False,
) -> Module:
    cells = dict(cells or {})
    return Module(
        name=name,
        hdlname=hdlname,
        cells=cells,
        ports=dict(ports or {}),
        netnames=dict(netnames or {}),
        is_stub=(not cells) if is_stub is None else is_stub,
        is_top=is_top,
    )


def make_design(
    modules: Mapping[str, Module] | None = None,
    flavour: str = "mapped",
    top: str | None = None,
) -> Design:
    mods = dict(modules or {})
    if top is None:
        marked = [n for n, m in mods.items() if m.is_top and not m.is_stub]
        top = marked[0] if marked else next((n for n, m in mods.items() if not m.is_stub), None)
    return Design(modules=mods, flavour=flavour, top=top)


def write_netlist(tmp_path: Path, *, src_root_name: str = "synth") -> tuple[Path, Path]:
    """A tiny mapped netlist on disk, plus the RTL its `src` values point at.

    Returns `(netlist_path, src_root)`. Everything in it is deliberate: a design
    module, a submodule instance, a flop with a source range, a library stub, and a
    module port that aliases nothing.
    """
    src_root = tmp_path / src_root_name
    (src_root / "rtl").mkdir(parents=True, exist_ok=True)
    (src_root / "rtl" / "pe_child.v").write_text(
        "module pe_child(input clk, output q);\n  always_ff @(posedge clk) q <= ~q;\nendmodule\n",
        encoding="utf-8",
    )
    doc = {
        "creator": "Yosys 0.69+post",
        "modules": {
            "tt_um": {
                "attributes": {"top": "00000000000000000000000000000001"},
                "ports": {
                    "clk": {"direction": "input", "bits": [1]},
                    "q": {"direction": "output", "bits": [3]},
                },
                "cells": {
                    "u_child": {
                        "hide_name": 0,
                        "type": "pe_child",
                        "port_directions": {"clk": "input", "q": "output"},
                        "connections": {"clk": [1], "q": [3]},
                        "parameters": {},
                        "attributes": {"src": "rtl/pe_child.v:1.1-1.20"},
                    }
                },
                "netnames": {
                    "clk": {"hide_name": 0, "bits": [1]},
                    "q": {"hide_name": 0, "bits": [3]},
                },
            },
            "pe_child": {
                "attributes": {"hdlname": "pe_child"},
                "ports": {
                    "clk": {"direction": "input", "bits": [0]},
                    "q": {"direction": "output", "bits": [2]},
                },
                "cells": {
                    "$auto$ff.cc:337:slice$1": {
                        "hide_name": 1,
                        "type": "sg13g2_dfrbpq_1",
                        "port_directions": {"CLK": "input", "D": "input", "Q": "output"},
                        "connections": {"CLK": [0], "D": [7], "Q": [2]},
                        "parameters": {},
                        "attributes": {"src": "rtl/pe_child.v:2.3-2.40"},
                    }
                },
                "netnames": {"q": {"hide_name": 0, "bits": [2]}},
            },
            "sg13g2_dfrbpq_1": {
                "attributes": {"blackbox": "00000000000000000000000000000001"},
                "ports": {
                    "CLK": {"direction": "input", "bits": [0]},
                    "D": {"direction": "input", "bits": [1]},
                    "Q": {"direction": "output", "bits": [2]},
                },
                "cells": {},
                "netnames": {},
            },
            "sg13g2_nand2_1": {
                "attributes": {"blackbox": "00000000000000000000000000000001"},
                "ports": {
                    "A": {"direction": "input", "bits": [0]},
                    "B": {"direction": "input", "bits": [1]},
                    "Y": {"direction": "output", "bits": [2]},
                },
                "cells": {},
                "netnames": {},
            },
        },
    }
    netlist = tmp_path / "netlist.json"
    netlist.write_text(json.dumps(doc), encoding="utf-8")
    return netlist, src_root
