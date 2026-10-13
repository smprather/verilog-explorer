"""The structural observations worth showing, and the ones this flavour can prove.

WHY THIS EXISTS. A netlist can be asked hundreds of questions and can answer only some of
them. This module holds the ones worth asking — each one measured on the reference design
rather than guessed at — and it refuses to answer the rest.

Two rules are baked in:

* An observation's bug-ness usually lives in the RTL, not here. `pe_dru`'s two latches are
  a documented two-phase latch; 83 of the reference design's 85 constant-driven nets are
  `_unused*` sinks and `$func$` locals, and only two are real signals. The filter is part
  of the detection, because a detector that cannot survive one teaches its user to ignore it.
* A negative result may only be printed if the loaded flavour can compute it. A mapped
  netlist carries no width metadata at all, so "no width truncation" is not a thing it can
  say, and it does not say it.

And one rule about presentation: a finding is labelled with the module's **readable** name.
`$paramod\pe_ctrl\WORDS=s32'0…100` is a key, not a name, and a finding nobody can read is a
finding nobody acts on — which is the whole failure this tool exists to prevent.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from verilog_explorer.classify import FLOP, LATCH, MACRO, cell_kind
from verilog_explorer.model import FLAVOUR_MAPPED, Bit, Cell, Design, Module, is_const
from verilog_explorer.naming import is_auto_name, module_label, net_label
from verilog_explorer.nets import NetIndex

#: A structural fact that is wrong whatever the RTL meant.
ERROR = "error"
#: A structural fact whose bug-ness lives in the RTL — show it, do not accuse.
OBSERVATION = "observation"

#: An array that became state: a handful of flops is not worth calling a register file.
REGISTER_FILE_MIN_BITS = 4

_ARRAY = re.compile(r"^(?P<base>.+?)\[")


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing worth knowing about the design, and where it came from.

    `subject` is what a reader sees, so it is labelled with the readable module name.
    `module` is the module key, which is how the viewer groups findings under a module.
    """

    code: str
    subject: str
    detail: str
    klass: str
    where: str | None = None
    module: str = ""


def detect(design: Design, *, per_module: Mapping[str, NetIndex] | None = None) -> list[Finding]:
    """Every finding for this design, cheapest-first per module."""
    indices = per_module or {}
    findings: list[Finding] = []
    for module in design.modules.values():
        if module.is_stub:
            continue
        index = indices.get(module.name) or NetIndex(module, design)
        findings.extend(_sequential_and_macros(module, design))
        findings.extend(_dead_nets(module, index))
        findings.extend(_constant_nets(module))
        findings.extend(_register_files(module, design))
        findings.extend(_undriven_outputs(module))
        findings.extend(_multiple_drivers(module))
    return findings


def negative_results(design: Design) -> list[str]:
    """What was checked and came back clean, with the counts behind each statement.

    Only for a mapped netlist: these checks read the cell vocabulary, and on a netlist
    that has not been through the same flow they would be answering a different question.
    """
    if design.flavour != FLAVOUR_MAPPED:
        return []
    modules = [m for m in design.modules.values() if not m.is_stub]
    findings = detect(design)
    multi = sum(1 for f in findings if f.code == "multiple-drivers")
    undriven = sum(1 for f in findings if f.code == "undriven-output")
    driven_bits = len(
        {
            (module.name, bit)
            for module in modules
            for cell in module.cells.values()
            for bit in cell.bits_in("output")
            if not is_const(bit)
        }
    )
    output_ports = sum(
        1 for module in modules for port in module.ports.values() if port.direction == "output"
    )
    return [
        f"no multiple drivers ({multi} of {driven_bits} driven bits are driven twice)",
        f"no undriven outputs ({undriven} of {output_ports} output ports lack a driver)",
    ]


def _subject(module: Module, name: str) -> str:
    """`pe_ctrl.resp_buf` — the readable label, never the `$paramod…` key."""
    return f"{module_label(module)}.{name}"


def _sequential_and_macros(module: Module, design: Design) -> list[Finding]:
    findings: list[Finding] = []
    for cell in module.cells.values():
        kind = cell_kind(cell, design)
        if kind == LATCH:
            findings.append(
                Finding(
                    code="latch",
                    subject=_subject(module, cell.name),
                    detail=f"{cell.type} holds state and is neither a flop nor a memory",
                    klass=OBSERVATION,
                    where=cell.src,
                    module=module.name,
                )
            )
        elif kind == MACRO:
            findings.append(
                Finding(
                    code="macro",
                    subject=_subject(module, cell.name),
                    detail=(
                        f"{cell.type} is a blackbox macro: there is no logic behind it to expand"
                    ),
                    klass=OBSERVATION,
                    where=cell.src,
                    module=module.name,
                )
            )
    return findings


def _dead_nets(module: Module, index: NetIndex) -> list[Finding]:
    return [
        Finding(
            code="dead-net",
            subject=_subject(module, net.name),
            detail="no cell in this module reads it",
            klass=OBSERVATION,
            module=module.name,
        )
        for net in index.dead_nets()
        if not is_auto_name(net.name)
    ]


def _constant_nets(module: Module) -> list[Finding]:
    return [
        Finding(
            code="constant-net",
            subject=_subject(module, net.name),
            detail=f"driven to the constant {net.bits[0]}, not to a cell output",
            klass=OBSERVATION,
            module=module.name,
        )
        for net in module.netnames.values()
        if not net.hide_name
        and not is_auto_name(net.name)
        and net.bits
        and all(is_const(bit) for bit in net.bits)
    ]


def _register_files(module: Module, design: Design) -> list[Finding]:
    """State that the RTL calls an array and synthesis built out of flops."""
    bits: dict[str, set[Bit]] = defaultdict(set)
    flops: dict[str, int] = defaultdict(int)
    for cell in module.cells.values():
        if cell_kind(cell, design) != FLOP:
            continue
        for bit in cell.bit_of("Q"):
            if is_const(bit):
                continue
            match = _ARRAY.match(net_label(module, bit))
            if not match:
                continue
            base = match["base"]
            bits[base].add(bit)
            flops[base] += 1
    return [
        Finding(
            code="register-file",
            subject=_subject(module, base),
            detail=(
                f"{len(width)} bits of state held in {flops[base]} flops: the RTL calls "
                "this an array, and synthesis built a register file rather than memory"
            ),
            klass=OBSERVATION,
            module=module.name,
        )
        for base, width in bits.items()
        if len(width) >= REGISTER_FILE_MIN_BITS
    ]


def _driven_bits(module: Module) -> set[Bit]:
    """Bits a cell drives, plus the module's own input-port bits, plus constants."""
    driven: set[Bit] = set()
    for cell in module.cells.values():
        driven.update(bit for bit in cell.bits_in("output") if not is_const(bit))
        driven.update(bit for bit in cell.bits_in("inout") if not is_const(bit))
    for port in module.ports.values():
        if port.direction in ("input", "inout"):
            driven.update(bit for bit in port.bits if not is_const(bit))
    return driven


def _undriven_outputs(module: Module) -> list[Finding]:
    driven = _driven_bits(module)
    return [
        Finding(
            code="undriven-output",
            subject=_subject(module, port.name),
            detail=(
                "no cell drives it, it aliases no module input, and it is not tied to a constant"
            ),
            klass=ERROR,
            module=module.name,
        )
        for port in module.ports.values()
        if port.direction == "output"
        and [bit for bit in port.bits if not is_const(bit)]
        and not any(bit in driven for bit in port.bits)
    ]


def _multiple_drivers(module: Module) -> list[Finding]:
    drivers: dict[Bit, list[Cell]] = defaultdict(list)
    for cell in module.cells.values():
        for bit in cell.bits_in("output"):
            if not is_const(bit):
                drivers[bit].append(cell)
    return [
        Finding(
            code="multiple-drivers",
            subject=_subject(module, net_label(module, bit)),
            detail=f"{len(cells)} cells drive this bit: {', '.join(c.type for c in cells)}",
            klass=ERROR,
            module=module.name,
        )
        for bit, cells in drivers.items()
        if len(cells) > 1
    ]
