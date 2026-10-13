"""Design, tree and page: one self-contained HTML document.

WHY THIS EXISTS. The alternative to a generated page is a server, and a server turns
"look at this netlist" into an install, a port and a process. One file you can open,
scp or commit is worth more than any of that for a browser you use to understand a
design — and it means the artifact can be diffed and gated later.

Two things this module is careful about:

* **It never states what the data does not support.** A gate with no source is labelled
  as such on the page, not silently linked to a guess; the flavour is stated because
  the checks that passed depend on it.
* **The model, not the markup, carries the design.** The page is data plus a small
  viewer, so everything a reader sees is inspectable in one JSON block.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict

from verilog_explorer.assets import CSS, JS, PAGE
from verilog_explorer.classify import FLOP, LATCH, MACRO, cell_kind
from verilog_explorer.detect import Finding, detect, negative_results
from verilog_explorer.hierarchy import Node, build_tree
from verilog_explorer.model import Cell, Design, Module
from verilog_explorer.naming import module_label, net_label
from verilog_explorer.nets import NetIndex
from verilog_explorer.source import SourceIndex

#: How many cell types and nets to show per module before summarising the rest.
MAX_TYPES = 12
MAX_NETS = 12
#: How many lines of a source range to carry into the page.
MAX_SOURCE_LINES = 200


def render_html(
    design: Design,
    *,
    sources: SourceIndex | None = None,
    title: str | None = None,
) -> str:
    """The whole page for this design, ready to write to disk."""
    tree = build_tree(design)
    findings = detect(design)
    negatives = negative_results(design) if design.flavour == "mapped" else []
    model = {
        "title": title or "verilog-explorer",
        "flavour": design.flavour,
        "top": design.top,
        "modules": [_module_view(m, design, sources) for m in _design_modules(design)],
        "instances": _flatten(tree),
        "findings": [asdict(f) for f in findings],
        "negatives": negatives,
    }
    return _page(model)


def source_coverage(design: Design, sources: SourceIndex) -> tuple[int, int]:
    """How many cells carry a source range, and how many of those resolve.

    A netlist whose paths resolve to nothing means the wrong root was handed over, and
    silently rendering a page with no sources is the wrong thing to do quietly.
    """
    claimed = resolved = 0
    for module in _design_modules(design):
        for cell in module.cells.values():
            if cell.src:
                claimed += 1
                if sources.locate(cell.src) is not None:
                    resolved += 1
    return claimed, resolved


def _design_modules(design: Design) -> list[Module]:
    return [m for m in design.modules.values() if not m.is_stub and m is not None]


def _flatten(node: Node | None) -> list[dict[str, str]]:
    if node is None:
        return []
    rows = [{"path": node.path, "label": node.label, "module": node.module}]
    for child in node.children:
        rows.extend(_flatten(child))
    return rows


def _module_view(module: Module, design: Design, sources: SourceIndex | None) -> dict[str, object]:
    index = NetIndex(module, design)
    flops = latches = macros = 0
    types: Counter[str] = Counter()
    for cell in module.cells.values():
        kind = cell_kind(cell, design)
        if kind == FLOP:
            flops += 1
        elif kind == LATCH:
            latches += 1
        elif kind == MACRO:
            macros += 1
        types[cell.type] += 1

    instances = [
        {"name": name, "label": name, "module": cell.type}
        for name, cell in module.cells.items()
        if not _is_leaf(cell, design)
    ]
    return {
        "key": module.name,
        "label": module_label(module),
        "badges": _badges(module),
        "cells": len(module.cells),
        "flops": flops,
        "latches": latches,
        "macros": macros,
        "instances": instances,
        "types": _top_types(types),
        "nets": _top_nets(index, module),
        "source": _source_view(module, sources),
    }


def _badges(module: Module) -> list[str]:
    from verilog_explorer.naming import parameter_badges

    return parameter_badges(module)


def _is_leaf(cell: Cell, design: Design) -> bool:
    target = design.modules.get(cell.type)
    return target is None or target.is_stub


def _top_types(types: Counter[str]) -> list[list[object]]:
    ranked = types.most_common()
    shown = [[name, count] for name, count in ranked[:MAX_TYPES]]
    if len(ranked) > MAX_TYPES:
        rest = sum(count for _, count in ranked[MAX_TYPES:])
        shown.append([f"{len(ranked) - MAX_TYPES} more types", rest])
    return shown


def _top_nets(index: NetIndex, module: Module) -> list[list[object]]:
    rows: list[tuple[str, int]] = []
    for net in module.netnames.values():
        if net.hide_name:
            continue
        loads = sum(len(index.loads(bit)) for bit in net.bits)
        rows.append((net_label(module, net.bits[0]) if net.bits else net.name, loads))
    rows.sort(key=lambda row: (-row[1], row[0]))
    return [[name, loads] for name, loads in rows[:MAX_NETS]]


def _source_view(module: Module, sources: SourceIndex | None) -> dict[str, object] | None:
    if sources is None:
        return None
    ranges = [sources.locate(cell.src) for cell in module.cells.values() if cell.src]
    locations = [loc for loc in ranges if loc is not None]
    if not locations:
        return None
    first = min(loc.first_line for loc in locations)
    last = max(loc.last_line for loc in locations)
    path = locations[0].path
    lines = (sources.lines(path) or [])[first - 1 : last]
    return {
        "path": str(path),
        "first": first,
        "last": last,
        "lines": lines[:MAX_SOURCE_LINES],
    }


def _page(model: dict[str, object]) -> str:
    from json import dumps

    payload = dumps(model, separators=(",", ":"), sort_keys=True).replace("</", "<\\/")
    return (
        PAGE.replace("__TITLE__", _text(str(model["title"])))
        .replace("__CSS__", CSS)
        .replace("__MODEL__", payload)
        .replace("__JS__", JS)
    )


def _text(value: str) -> str:
    # Titles come from the command line and land in <title>, so keep the shell of the
    # page valid.
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def findings_for(findings: Sequence[Finding], module: str) -> list[Finding]:
    """The findings that belong to one module."""
    return [f for f in findings if f.subject.startswith(module)]
