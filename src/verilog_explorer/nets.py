"""Per-module drivers, loads, and the boundary of a module.

WHY THIS EXISTS. "What drives this net, and what does it feed?" is the question a
netlist browser exists to answer, and the obvious implementation of it is wrong.

The first measurement of the reference design reported 160 undriven outputs, and all
160 were healthy: `assign io_port = arg[3:0]` leaves a port sharing a bit index with
the net it aliases, so no cell drives it and yet it is perfectly driven. The lesson
is that bit indices are the currency here — a name-based answer is wrong whenever a
port aliases a net, which in a real design is often.

The second lesson is that a module's own input ports are *sources* at its boundary.
Without that, every alias to an input reads as floating.
"""

from __future__ import annotations

from collections import defaultdict

from verilog_explorer.model import Bit, Cell, Design, Module, Net, bit_key, is_const

#: Boundary marker for a bit that is a constant.
BOUNDARY_CONST = "const"
#: Boundary marker prefix for a bit owned by the module's own input port.
BOUNDARY_PORT = "port:"


class NetIndex:
    """Drivers and loads, per bit, inside one module.

    Every lookup is by **bit**, never by name, because a bit may carry several names
    and a name may repeat a bit.
    """

    def __init__(self, module: Module, design: Design | None = None) -> None:
        self.module = module
        self.design = design
        self._drivers: dict[str, tuple[Cell, ...]] = {}
        self._loads: dict[str, tuple[Cell, ...]] = {}
        self._boundary: dict[str, str] = {}
        self._external: frozenset[str] = frozenset()
        self._build()

    def _build(self) -> None:
        drivers: dict[str, list[Cell]] = defaultdict(list)
        loads: dict[str, list[Cell]] = defaultdict(list)
        for cell in self.module.cells.values():
            for port, bits in cell.connections.items():
                direction = cell.port_directions.get(port)
                if direction not in ("input", "output", "inout"):
                    continue
                keys = [bit_key(bit) for bit in bits]
                if direction in ("output", "inout"):
                    for key in keys:
                        drivers[key].append(cell)
                if direction in ("input", "inout"):
                    for key in keys:
                        loads[key].append(cell)

        boundary: dict[str, str] = {}
        external: set[str] = set()
        for port in self.module.ports.values():
            keys = [bit_key(bit) for bit in port.bits]
            if port.direction in ("input", "inout"):
                for key in keys:
                    boundary.setdefault(key, f"{BOUNDARY_PORT}{port.name}")
            elif port.direction == "output":
                # Something outside the module reads this bit, so it is a load.
                external.update(keys)

        self._drivers = {key: tuple(cells) for key, cells in drivers.items()}
        self._loads = {key: tuple(cells) for key, cells in loads.items()}
        self._boundary = boundary
        self._external = frozenset(external)

    def drivers(self, bit: Bit) -> tuple[Cell, ...]:
        """Cells inside this module that drive `bit`."""
        return self._drivers.get(bit_key(bit), ())

    def loads(self, bit: Bit) -> tuple[Cell, ...]:
        """Cells inside this module that read `bit`."""
        return self._loads.get(bit_key(bit), ())

    def boundary(self, bit: Bit) -> str | None:
        """Why `bit` is driven with no cell in sight: a constant, or a module input."""
        if is_const(bit):
            return BOUNDARY_CONST
        return self._boundary.get(bit_key(bit))

    def dead_nets(self) -> tuple[Net, ...]:
        """Named, visible nets that nothing inside this module reads.

        An observation, not an error: dead debug taps and deliberately unused outputs
        are common, and only the RTL can say which of these were meant to be read.
        """
        return tuple(
            net
            for net in self.module.netnames.values()
            if not net.hide_name and net.bits and all(self._is_unloaded(bit) for bit in net.bits)
        )

    def _is_unloaded(self, bit: Bit) -> bool:
        if is_const(bit):
            return False
        key = bit_key(bit)
        if self._loads.get(key):
            return False
        if key in self._external:
            return False
        if key in self._boundary:
            return False
        return True

    def parent_hint(self, port: str) -> str | None:
        """`u_soc.imem_addr` — the instance outside this module that owns `port`.

        One hop only, and cheap: the tree already knows the parent relation, and this
        turns "the driver is somewhere above" into a name. Following the net further
        needs a cross-module index and is not day one.
        """
        if self.design is None:
            return None
        for module in self.design.modules.values():
            if module.is_stub:
                continue
            for cell in module.cells.values():
                if cell.type == self.module.name and port in cell.connections:
                    return f"{cell.name}.{port}"
        return None
