"""The in-memory model of a netlist.

Three facts about the yosys JSON format shape everything here, and each of them
cost a wrong measurement before it was written down:

* A bit is a **string**: ``"12"`` is a module-local bit index, and ``"0" "1" "x"
  "z"`` are constants. Keeping both as strings avoids an int/str union in every
  consumer.
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

CONST_BITS = frozenset({"0", "1", "x", "z"})

FLAVOUR_MAPPED = "mapped"
FLAVOUR_RTLISH = "rtl-ish"
FLAVOUR_UNKNOWN = "unknown"


def is_const(bit: str) -> bool:
    """True when a bit entry is a constant rather than a bit index."""
    return bit in CONST_BITS


@dataclass(frozen=True, slots=True)
class Cell:
    """One instance in a module: a submodule, a library cell, or an operator."""

    name: str
    type: str
    src: str | None = None
    connections: dict[str, tuple[str, ...]] = field(default_factory=dict)
    port_directions: dict[str, str] = field(default_factory=dict)
    parameters: dict[str, str] = field(default_factory=dict)

    def bits_in(self, direction: str) -> tuple[str, ...]:
        """Every bit this cell touches through a port of the given direction."""
        found: list[str] = []
        for port, bits in self.connections.items():
            if self.port_directions.get(port) == direction:
                found.extend(bits)
        return tuple(found)

    def bit_of(self, port: str) -> tuple[str, ...]:
        """The bits on one named port, or an empty tuple when absent."""
        return self.connections.get(port, ())


@dataclass(frozen=True, slots=True)
class Port:
    name: str
    direction: str
    bits: tuple[str, ...]
    signed: bool = False


@dataclass(frozen=True, slots=True)
class Net:
    name: str
    bits: tuple[str, ...]
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
