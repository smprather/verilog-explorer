"""Factories for building netlist models in tests without running yosys.

Tasks 2-7 all need a `Module` with a couple of cells and nets in it. Building one
by hand in every test buried the assertion under the setup, so the shapes live here.

Bit arguments follow the format: pass an **int** for a bit index and a **str** for
a constant.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

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
