"""Hierarchy tests.

Hierarchy is **inferred**, never assumed: this module is the single seam where a
tree comes out of a model. Today it reads module-instance cells; a flat gate-level
netlist, where the hierarchy survives only as `/`-separated instance names, is a
second strategy behind the same function, not a rewrite.
"""

from __future__ import annotations

from tests.factories import make_cell, make_design, make_module
from verilog_explorer.hierarchy import build_tree

GATE = make_cell("u_g", "sg13g2_inv_1")


def test_tree_root_is_the_top_module():
    d = make_design(
        {
            "top": make_module(
                "top", hdlname="top", is_top=True, cells={"u_a": make_cell("u_a", "child")}
            ),
            "child": make_module("child", hdlname="child", cells={"u_g": GATE}),
            "sg13g2_inv_1": make_module("sg13g2_inv_1"),
        }
    )
    tree = build_tree(d)
    assert tree is not None
    assert tree.module == "top"
    assert tree.label == "top"
    assert tree.path == "top"


def test_tree_follows_instance_cells():
    d = make_design(
        {
            "top": make_module(
                "top", hdlname="top", is_top=True, cells={"u_a": make_cell("u_a", "child")}
            ),
            "child": make_module("child", hdlname="child", cells={"u_g": GATE}),
            "sg13g2_inv_1": make_module("sg13g2_inv_1"),
        }
    )
    tree = build_tree(d)
    assert tree is not None
    assert [c.path for c in tree.children] == ["top/u_a"]
    assert tree.children[0].module == "child"
    assert tree.children[0].label == "u_a"


def test_the_same_module_instantiated_twice_gives_two_distinct_paths():
    d = make_design(
        {
            "top": make_module(
                "top",
                hdlname="top",
                is_top=True,
                cells={
                    "u_rx_codec": make_cell("u_rx_codec", "codec"),
                    "u_tx_codec": make_cell("u_tx_codec", "codec"),
                },
            ),
            "codec": make_module("codec", hdlname="codec", cells={"u_g": GATE}),
            "sg13g2_inv_1": make_module("sg13g2_inv_1"),
        }
    )
    tree = build_tree(d)
    assert tree is not None
    assert [c.path for c in tree.children] == ["top/u_rx_codec", "top/u_tx_codec"]
    assert {c.module for c in tree.children} == {"codec"}


def test_a_library_cell_is_not_a_hierarchy_node():
    d = make_design(
        {
            "top": make_module(
                "top",
                hdlname="top",
                is_top=True,
                cells={
                    "u_g1": make_cell("u_g1", "sg13g2_nand2_1"),
                    "u_sub": make_cell("u_sub", "child"),
                },
            ),
            "child": make_module("child", hdlname="child", cells={"u_g": GATE}),
            "sg13g2_nand2_1": make_module("sg13g2_nand2_1"),
            "sg13g2_inv_1": make_module("sg13g2_inv_1"),
        }
    )
    tree = build_tree(d)
    assert tree is not None
    assert [c.label for c in tree.children] == ["u_sub"]


def test_recursive_instantiation_does_not_hang():
    d = make_design(
        {
            "top": make_module(
                "top", hdlname="top", is_top=True, cells={"u_self": make_cell("u_self", "top")}
            ),
        }
    )
    tree = build_tree(d)
    assert tree is not None
    assert tree.children[0].module == "top"
    assert tree.children[0].children == ()


def test_a_design_with_no_top_returns_none():
    assert build_tree(make_design({"sg13g2_inv_1": make_module("sg13g2_inv_1")})) is None
