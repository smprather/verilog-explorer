"""Decide what a cell is, from its ports rather than its name.

WHY THIS EXISTS. The page's header says "1,714 flops, 2 latches" and the tree badges
modules with them, so something has to decide what a flop is. A hand-typed list of
cell names drifts the moment the library or the flow changes — and it cannot span
both netlist flavours, where the same storage element is `sg13g2_dfrbpq_1` in one and
`$dff` in the other. The port signature can, and it also survives the fact that in a
mapped netlist a register's instance name is `$auto$ff.cc:337:slice$28794`, which
says nothing at all.
"""

from __future__ import annotations

from verilog_explorer.model import Cell, Design

#: Ports that mean "captured on an edge".
CLOCK_PORTS = frozenset({"CLK", "C", "CK"})
#: Ports that mean "transparent while asserted".
GATE_PORTS = frozenset({"G", "EN", "E"})
DATA_IN = "D"
DATA_OUT = "Q"

#: Cell-type prefixes that are library or internal logic rather than a macro.
LIBRARY_TYPE_PREFIXES = ("sg13g2_", "$")

INSTANCE = "instance"
FLOP = "flop"
LATCH = "latch"
MACRO = "macro"
GATE = "gate"


def cell_kind(cell: Cell, design: Design) -> str:
    """One of `instance`, `flop`, `latch`, `macro`, `gate`."""
    module = design.modules.get(cell.type)
    if module is not None and not module.is_stub:
        return INSTANCE
    if module is not None and not cell.type.startswith(LIBRARY_TYPE_PREFIXES):
        # A stub module that is not a standard cell: a blackbox macro such as the
        # SRAM, with no logic behind it to expand.
        return MACRO
    ports = set(cell.connections)
    if DATA_IN in ports and DATA_OUT in ports:
        if ports & CLOCK_PORTS:
            return FLOP
        if ports & GATE_PORTS:
            return LATCH
    return GATE


def is_sequential(kind: str) -> bool:
    """State-holding cells, which is what the header counts."""
    return kind in (FLOP, LATCH)
