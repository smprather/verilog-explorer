"""Read a yosys JSON netlist into the model.

WHY THIS EXISTS. Every downstream question starts with "what is actually in this
file", and the answer is not the obvious one. yosys emits a *stub module* for every
library cell, so a naive "is this cell's type in ``modules``?" classifies all 9,965
stdcells of the reference design as submodule instances and reports zero leaf
cells. This module is the single place that distinction is made.

It also decides the **flavour** of the netlist from the data rather than from a
flag: which cell vocabulary is present. That matters because the two flavours
answer different questions — a mapped netlist carries no width metadata, so a
width-truncation check is not available on it and must never be claimed.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from verilog_explorer.model import (
    FLAVOUR_MAPPED,
    FLAVOUR_RTLISH,
    FLAVOUR_UNKNOWN,
    Bit,
    Cell,
    Design,
    Module,
    Net,
    Port,
)

# Cell types and stub names only a mapped netlist has.
MAPPED_PREFIXES = ("sg13g2_", "RM_")
# A `$`-prefixed cell type that is not a module in the document is an operator
# cell ($add, $dff, $dlatch). `$paramod...` names ARE modules and prove nothing.
OPERATOR_PREFIX = "$"


class NotANetlistError(Exception):
    """The path could not be read, is not JSON, or is not a netlist."""


def load_design(path: Path | str) -> Design:
    """Read `path` and return the model. Raises NotANetlistError on bad input."""
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise NotANetlistError(f"cannot read {path}: {exc.strerror or exc}") from exc
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise NotANetlistError(f"{path} is not JSON: {exc}") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("modules"), dict):
        raise NotANetlistError(
            f"{path} has no 'modules' object, so it is not a yosys JSON netlist"
        )
    modules = {
        str(name): _module(str(name), body)
        for name, body in doc["modules"].items()
        if isinstance(body, dict)
    }
    return Design(
        modules=modules,
        flavour=detect_flavour(modules),
        top=_top_name(modules),
        source_path=path,
    )


def detect_flavour(modules: Mapping[str, Module]) -> str:
    """`"mapped"`, `"rtl-ish"` or `"unknown"`, decided from the cell vocabulary.

    Decided by **cell types only**, never by module names. `read_liberty -lib` loads the
    liberty cells into the document before `proc` runs, so mapped stub modules are present
    in both flavours and prove nothing; only a cell that actually instantiates one does.
    """
    mapped = False
    operator = False
    for module in modules.values():
        for cell in module.cells.values():
            if cell.type.startswith(MAPPED_PREFIXES):
                mapped = True
            elif cell.type.startswith(OPERATOR_PREFIX) and cell.type not in modules:
                operator = True
    if mapped:
        return FLAVOUR_MAPPED
    if operator:
        return FLAVOUR_RTLISH
    return FLAVOUR_UNKNOWN


def _module(name: str, body: Mapping[str, Any]) -> Module:
    attributes = body.get("attributes") or {}
    cells = {
        str(cell_name): _cell(str(cell_name), cell)
        for cell_name, cell in (body.get("cells") or {}).items()
        if isinstance(cell, dict)
    }
    ports = {
        str(port_name): Port(
            name=str(port_name),
            direction=str(port.get("direction", "input")),
            bits=_bits(port.get("bits")),
            signed=_truthy(port.get("signed")),
        )
        for port_name, port in (body.get("ports") or {}).items()
        if isinstance(port, dict)
    }
    netnames = {
        str(net_name): Net(
            name=str(net_name),
            bits=_bits(net.get("bits")),
            hide_name=_truthy(net.get("hide_name")),
        )
        for net_name, net in (body.get("netnames") or {}).items()
        if isinstance(net, dict)
    }
    hdlname = attributes.get("hdlname")
    return Module(
        name=name,
        hdlname=str(hdlname) if hdlname else None,
        cells=cells,
        ports=ports,
        netnames=netnames,
        is_stub=not cells,
        is_top=_truthy(attributes.get("top")),
    )


def _cell(name: str, body: Mapping[str, Any]) -> Cell:
    src = (body.get("attributes") or {}).get("src")
    return Cell(
        name=name,
        type=str(body.get("type", "")),
        src=str(src) if src else None,
        connections={
            str(port): _bits(bits)
            for port, bits in (body.get("connections") or {}).items()
        },
        port_directions={
            str(port): str(direction)
            for port, direction in (body.get("port_directions") or {}).items()
        },
        parameters={str(k): str(v) for k, v in (body.get("parameters") or {}).items()},
    )


def _bits(value: Any) -> tuple[Bit, ...]:
    """A connection or net bit list as strings, in the document's own order.

    Indices arrive as JSON numbers and stay ints; constants arrive as JSON
    strings and stay strings. That distinction is the only thing separating index
    0 from the constant 0, so it is preserved rather than normalised away.
    """
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(bit if isinstance(bit, int) else str(bit) for bit in value)


def _truthy(value: Any) -> bool:
    """yosys writes attribute booleans as 32-bit binary strings, not true/1."""
    if value is None or value is False:
        return False
    if value is True:
        return True
    if isinstance(value, int):
        return value != 0
    return "1" in str(value)


def _top_name(modules: Mapping[str, Module]) -> str | None:
    """The module `hierarchy -top` marked, if the document records one."""
    for name, module in modules.items():
        if module.is_top and not module.is_stub:
            return name
    return None
