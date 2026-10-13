"""Readable names for a design whose real names are unreadable.

WHY THIS EXISTS. Synthesis takes the names away. A module becomes
`$paramod\\pe_ctrl\\WORDS=s32'00000000000000000000010000000000`, a register becomes
`$auto$ff.cc:337:slice$28794`, and a net becomes `$abc$67326$new_n1627`. A viewer
that prints those strings is unusable, and the design's own labels are still in
the file — yosys keeps `attributes.hdlname` on every parameter-derived module.

Two rules this module exists to enforce:

* The raw key is never the label. `pe_ctrl` is the label; `WORDS=1024` is a badge.
* A cell's instance name is not its name. In a mapped netlist the instance is
  `$auto$ff.cc:337:slice$28794`, and the only human word for that register is the
  net on its `Q` — which is why `net_label` exists and why the net pane is not
  decoration.
"""

from __future__ import annotations

import re

from verilog_explorer.model import Bit, Module, is_const

# `$paramod\pe_ctrl\WORDS=…` and `$paramod$<40 hex>\pe_soc` both reduce to the
# source module name in group 2.
_MODULE_BASE = re.compile(r"^\$paramod(?:\$[0-9a-f]{40})?\\([^\\]+)")
# Everything after the base name: one `NAME=value` per `\`-separated field.
_PARAM_TAIL = re.compile(r"^\$paramod(?:\$[0-9a-f]{40})?\\[^\\]+\\?(.*)$")
# yosys writes parameters as `s32'00000000000000000000010000000000`.
_NUMBERED = re.compile(r"^[su]?\d*'([01_]+)$")

_AUTO_PREFIXES = ("$", "_unused")


def module_label(module: Module) -> str:
    """The name a human would use for this module."""
    if module.hdlname:
        return module.hdlname
    match = _MODULE_BASE.match(module.name)
    return match.group(1) if match else module.name


def parameter_badges(module: Module) -> list[str]:
    """`["WORDS=1024"]` — the module's parameters, readable, for a label badge."""
    match = _PARAM_TAIL.match(module.name)
    if not match:
        return []
    tail = match.group(1)
    badges: list[str] = []
    for field in [f for f in tail.split("\\") if f]:
        name, _, value = field.partition("=")
        badges.append(f"{name}={decode_param(value)}" if value else field)
    return badges


def decode_param(value: str) -> str:
    """`s32'0000…0100` becomes `1024`; anything else is kept verbatim."""
    numbered = _NUMBERED.match(value)
    if numbered:
        return str(int(numbered.group(1).replace("_", ""), 2))
    return value


def is_auto_name(name: str) -> bool:
    """True for the names synthesis invented, which no human chose."""
    return name.startswith(_AUTO_PREFIXES)


def format_bits(bits: tuple[Bit, ...]) -> str:
    """A compact description of a bit list: `3:0`, `10 bits`, `340`, `0`.

    The list is **unsorted and LSB-first by position**, so a copy is sorted only
    to test for contiguity; the stored order is never changed and the width is
    never assumed from `len(bits)` alone. Constants are strings and indices are
    ints, so index 0 and the constant 0 stay distinguishable.
    """
    if not bits:
        return "?"
    if len(bits) == 1:
        return f"{bits[0]}"
    if all(is_const(bit) for bit in bits):
        return f"{bits[0]}"
    indices = sorted(int(bit) for bit in bits if not is_const(bit))
    if not indices:
        return "?"
    if len(indices) == 1:
        return str(indices[0])
    high, low = indices[-1], indices[0]
    if len(indices) == high - low + 1:
        return f"{high}:{low}"
    return f"{len(indices)} bits"


def net_label(module: Module, bit: Bit) -> str:
    """The best human name for one bit, or `bit N` when the design has none.

    A bit may carry several names and a name may repeat a bit, so this asks every
    netname whose bits contain the bit, prefers a name a human chose, and prefers
    the shortest among equals.
    """
    candidates = [net.name for net in module.netnames.values() if bit in net.bits]
    if not candidates:
        return f"bit {bit}"
    human = [name for name in candidates if not is_auto_name(name)]
    if human:
        return min(human, key=len)
    return min(candidates, key=len)
