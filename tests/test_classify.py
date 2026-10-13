"""Classification tests.

WHY THIS EXISTS. The header says "1,714 flops, 2 latches" and the tree badges a
module with them, so something has to decide what a flop is. A hand-typed list of
cell names drifts the moment the library or the flow changes, so the classifier
reads the port signature: a clock plus a data input and a data output is a flop; a
gate or enable with no clock is a latch.

The same signature has to work in both netlist flavours, where the very same
storage element is `sg13g2_dfrbpq_1` in one and `$dff` in the other.
"""

from __future__ import annotations

from tests.factories import make_cell, make_design, make_module
from verilog_explorer.classify import cell_kind


def design():
    return make_design(
        {
            "top": make_module(
                "top",
                hdlname="top",
                is_top=True,
                cells={"u_g": make_cell("u_g", "sg13g2_inv_1")},
            ),
            "sg13g2_dfrbpq_1": make_module("sg13g2_dfrbpq_1"),
            "sg13g2_dlhq_1": make_module("sg13g2_dlhq_1"),
            "sg13g2_nand2_1": make_module("sg13g2_nand2_1"),
            "sg13g2_inv_1": make_module("sg13g2_inv_1"),
            "RM_IHPSG13_1P_1024x16_c2_bm_bist": make_module("RM_IHPSG13_1P_1024x16_c2_bm_bist"),
            "pe_cpu": make_module(
                "pe_cpu",
                hdlname="pe_cpu",
                cells={"u_g": make_cell("u_g", "sg13g2_inv_1")},
            ),
        }
    )


def test_a_reset_flop_is_a_flop():
    cell = make_cell(
        "u_ff",
        "sg13g2_dfrbpq_1",
        connections={"CLK": (1,), "D": (2,), "Q": (3,), "RESET_B": (4,)},
        port_directions={"CLK": "input", "D": "input", "Q": "output", "RESET_B": "input"},
    )
    assert cell_kind(cell, design()) == "flop"


def test_a_level_sensitive_cell_is_a_latch():
    cell = make_cell(
        "u_la",
        "sg13g2_dlhq_1",
        connections={"D": (2,), "G": (1,), "Q": (3,)},
        port_directions={"D": "input", "G": "input", "Q": "output"},
    )
    assert cell_kind(cell, design()) == "latch"


def test_the_ihp_library_names_the_enable_gate():
    # The reference design's two pe_dru latches are sg13g2_dlhq_1 with ports D/GATE/Q.
    # A fixture that guessed `G` classified them as plain gates, and the real-design
    # acceptance test is what caught it.
    cell = make_cell(
        "$auto$ff.cc:337:slice$28012",
        "sg13g2_dlhq_1",
        src="rtl/pe_dru.v:185.15-185.15",
        connections={"D": (4,), "GATE": (2,), "Q": (170,)},
        port_directions={"D": "input", "GATE": "input", "Q": "output"},
    )
    assert cell_kind(cell, design()) == "latch"


def test_the_rtl_ish_flavour_classifies_the_same_way():
    d = design()
    flip = make_cell("$procdff$1", "$dff", connections={"CLK": (1,), "D": (2,), "Q": (3,)})
    latch = make_cell("$procdlatch$1", "$dlatch", connections={"EN": (1,), "D": (2,), "Q": (3,)})
    assert cell_kind(flip, d) == "flop"
    assert cell_kind(latch, d) == "latch"


def test_a_plain_gate_is_a_gate():
    cell = make_cell("u_g1", "sg13g2_nand2_1", connections={"A": (1,), "B": (2,), "Y": (3,)})
    assert cell_kind(cell, design()) == "gate"


def test_an_internal_operator_that_is_not_storage_is_a_gate():
    cell = make_cell("$add$1", "$add", connections={"A": (1,), "B": (2,), "Y": (3,)})
    assert cell_kind(cell, design()) == "gate"


def test_a_blackbox_macro_is_a_macro():
    cell = make_cell("u_sram", "RM_IHPSG13_1P_1024x16_c2_bm_bist", connections={"A_CLK": (1,)})
    assert cell_kind(cell, design()) == "macro"


def test_a_cell_typed_as_a_design_module_is_an_instance():
    cell = make_cell("u_cpu", "pe_cpu", connections={"clk": (1,)})
    assert cell_kind(cell, design()) == "instance"


def test_flop_detection_does_not_depend_on_the_cell_name():
    # In a mapped netlist the instance is `$auto$ff.cc:337:slice$28794`; the name
    # carries no information at all, which is why the ports decide.
    cell = make_cell(
        "$auto$ff.cc:337:slice$28794",
        "sg13g2_dfrbpq_1",
        connections={"CLK": (1,), "D": (2,), "Q": (3,)},
    )
    assert cell_kind(cell, design()) == "flop"
