"""Infer the design's hierarchy from the model.

WHY THIS EXISTS. Hierarchy is the one thing a netlist browser cannot take from the
file tree. A mapped netlist carries it as module instances; a flat gate-level
netlist carries it only inside instance-name paths (`u_soc/u_ctrl/fsm/state_reg[3]`),
and a million-cell flat netlist is a normal thing to be handed. Both are the same
tree to everything downstream, so the inference lives here — in one function —
and no consumer knows which strategy produced the tree.

Today: module instances. The `/`-path strategy is a second implementation behind
`build_tree`, not a change to any consumer.
"""

from __future__ import annotations

from dataclasses import dataclass

from verilog_explorer.model import Design
from verilog_explorer.naming import module_label


@dataclass(frozen=True, slots=True)
class Node:
    """One instance in the tree.

    `path` is identity (`u_soc/u_ctrl`) and stays unique even when one module is
    instantiated many times; `label` is what a human sees; `module` is the module
    key, whose label the reader can resolve separately.
    """

    path: str
    label: str
    module: str
    children: tuple[Node, ...] = ()


def build_tree(design: Design) -> Node | None:
    """The design's instance tree, or None when the document has no design module."""
    root_name = design.top or next(
        (name for name, module in design.modules.items() if not module.is_stub), None
    )
    if root_name is None or root_name not in design.modules:
        return None
    root = design.modules[root_name]
    return Node(
        path=root_name,
        label=module_label(root),
        module=root_name,
        children=_children(design, root_name, path=root_name, ancestors=(root_name,)),
    )


def _children(
    design: Design, module_name: str, *, path: str, ancestors: tuple[str, ...]
) -> tuple[Node, ...]:
    module = design.modules[module_name]
    nodes: list[Node] = []
    for cell in module.cells.values():
        child = design.modules.get(cell.type)
        if child is None or child.is_stub:
            # A library cell, a blackbox macro, or an operator cell: not hierarchy.
            continue
        child_path = f"{path}/{cell.name}"
        if cell.type in ancestors:
            # Recursive instantiation. Show the node, do not descend into it.
            nodes.append(Node(path=child_path, label=cell.name, module=cell.type))
            continue
        nodes.append(
            Node(
                path=child_path,
                label=cell.name,
                module=cell.type,
                children=_children(
                    design, cell.type, path=child_path, ancestors=(*ancestors, cell.type)
                ),
            )
        )
    return tuple(nodes)
