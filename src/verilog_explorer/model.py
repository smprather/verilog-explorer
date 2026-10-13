"""The in-memory model of a netlist.

Three facts about the yosys JSON format shape everything here, and each of them
cost a wrong measurement before it was written down:

* A bit is **either an int or a string**, and that is not a detail: yosys writes
  bit *indices* as JSON numbers and *constants* as JSON strings (``"0" "1" "x"
  "z"``). Stringifying both — the obvious simplification — makes bit 0 of every
  bus indistinguishable from the constant 0, so a signal on bit 0 reads as a
  constant and every fanout count that touches bit 0 is wrong. The model keeps
  the format's own distinction.
* Bit tuples are **unsorted and LSB-first by position**. Nothing in this package
  reorders them, and nothing assumes ``len(bits)`` is the signal's width.
* A bit may carry many names and one name may repeat a bit. No structure here
  builds a 1:1 bit-to-name map, because the format does not have one.

A module with no cells of its own is a **stub**: ``read_liberty -lib`` emits one
per library cell, so "is the type in ``modules``?" is true for every stdcell and
answers nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

#: A module-local bit index (int) or a constant (str).
Bit = int | str

#: The constant entries yosys writes; kept for documentation and for parsers that
#: stringify eagerly.
CONST_BITS = frozenset({"0", "1", "x", "z"})

FLAVOUR_MAPPED = "mapped"
FLAVOUR_RTLISH = "rtl-ish"
FLAVOUR_UNKNOWN = "unknown"


def is_const(bit: Bit) -> bool:
    """True when a bit entry is a constant rather than a bit index."""
    return isinstance(bit, str)


def bit_key(bit: Bit) -> str:
    """A stable, collision-free key for indexing a bit in a dict.

    ``bit_key(0) == "b0"`` for index 0 and ``bit_key("0") == "c0"`` for the
    constant, so the two can never collide.
    """
    return f"c{bit}" if isinstance(bit, str) else f"b{bit}"


@dataclass(frozen=True, slots=True)
class Cell:
    """One instance in a module: a submodule, a library cell, or an operator."""

    name: str
    type: str
    src: str | None = None
    connections: dict[str, tuple[Bit, ...]] = field(default_factory=dict)
    port_directions: dict[str, str] = field(default_factory=dict)
    parameters: dict[str, str] = field(default_factory=dict)

    def bits_in(self, direction: str) -> tuple[Bit, ...]:
        """Every bit this cell touches through a port of the given direction."""
        found: list[Bit] = []
        for port, bits in self.connections.items():
            if self.port_directions.get(port) == direction:
                found.extend(bits)
        return tuple(found)

    def bit_of(self, port: str) -> tuple[Bit, ...]:
        """The bits on one named port, or an empty tuple when absent."""
        return self.connections.get(port, ())


@dataclass(frozen=True, slots=True)
class Port:
    name: str
    direction: str
    bits: tuple[Bit, ...]
    signed: bool = False


@dataclass(frozen=True, slots=True)
class Net:
    name: str
    bits: tuple[Bit, ...]
    hide_name: bool = False


@dataclass(frozen=True, slots=True)
class Module:
    name: str
    hdlname: str | None
    cells: dict[str, Cell]
    ports: dict[str, Port]
    netnames: dict[str, Net]
    is_stub: bool
    is_top: bool = False

    def cell_count(self) -> int:
        """Cells of this module's own, regardless of kind."""
        return len(self.cells)


@dataclass(frozen=True, slots=True)
class Design:
    modules: dict[str, Module]
    flavour: str
    top: str | None
    source_path: Path | None = None

    def design_modules(self) -> dict[str, Module]:
        """Modules that carry logic, excluding library and blackbox stubs."""
        return {n: m for n, m in self.modules.items() if not m.is_stub}

    def stubs(self) -> dict[str, Module]:
        return {n: m for n, m in self.modules.items() if m.is_stub}
