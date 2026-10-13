"""Detection tests.

Every finding here is an **observation** whose bug-ness lives in the RTL, except the two
that are structural errors — and both of those were tuned against a measurement: the
first pass at "is this output driven?" reported 160 healthy outputs as undriven.

`pe_dru`'s two latches are a documented two-phase latch, and 83 of the reference design's
85 constant-driven nets are `_unused*` sinks and `$func$` locals. A detector that cannot
survive a filter teaches its user to ignore it, so most of these tests are about what must
*not* be reported.
"""

from __future__ import annotations

from dataclasses import replace

from tests.factories import make_cell, make_design, make_module, make_net, make_port
from verilog_explorer.detect import detect, negative_results
from verilog_explorer.model import Cell, Design, Module, Net

FLOPS = "sg13g2_dfrbpq_1"
LATCHES = "sg13g2_dlhq_1"
MACRO = "RM_IHPSG13_1P_1024x16_c2_bm_bist"
FLOP_SRC = "rtl/pe_ctrl.v:636.3-1326.6"


def flop(name: str, q_bit: int, d_bit: int, clk_bit: int = 1) -> Cell:
    return make_cell(
        name,
        FLOPS,
        src=FLOP_SRC,
        connections={"CLK": (clk_bit,), "D": (d_bit,), "Q": (q_bit,)},
        port_directions={"CLK": "input", "D": "input", "Q": "output"},
    )


def reader(name: str, bit: int, out: int) -> Cell:
    return make_cell(
        name,
        "sg13g2_nand2_1",
        connections={"A": (bit,), "B": (bit,), "Y": (out,)},
        port_directions={"A": "input", "B": "input", "Y": "output"},
    )


def latch() -> Cell:
    return make_cell(
        "u_la",
        LATCHES,
        src="rtl/pe_dru.v:185.5-188.9",
        connections={"D": (2,), "G": (1,), "Q": (3,)},
        port_directions={"D": "input", "G": "input", "Q": "output"},
    )


def stubs() -> dict[str, Module]:
    return {
        FLOPS: make_module(FLOPS),
        LATCHES: make_module(LATCHES),
        MACRO: make_module(MACRO),
    }


def design_with(module: Module) -> Design:
    # A module with no cells of its own is a library stub by definition, and detectors
    # skip those. These fixtures are design modules, so say so rather than padding them
    # with cells that would produce findings of their own.
    return make_design({module.name: replace(module, is_stub=False), **stubs()})


def test_an_inferred_latch_is_reported_with_its_source():
    module = make_module("pe_dru", hdlname="pe_dru", cells={"u_la": latch()})
    found = [f for f in detect(design_with(module)) if f.code == "latch"]
    assert len(found) == 1
    assert found[0].where == "rtl/pe_dru.v:185.5-188.9"
    assert "pe_dru" in found[0].subject


def test_a_blackbox_macro_is_reported():
    macro = make_cell("u_sram", MACRO, connections={"A_CLK": (1,)})
    module = make_module("pe_imem", hdlname="pe_imem", cells={"u_sram": macro})
    assert [f.subject for f in detect(design_with(module)) if f.code == "macro"] == [
        "pe_imem.u_sram"
    ]


def test_a_dead_named_net_is_reported():
    module = make_module(
        "pe_eth_tx", hdlname="pe_eth_tx", netnames={"crc_state": make_net("crc_state", (5, 6))}
    )
    found = [f for f in detect(design_with(module)) if f.code == "dead-net"]
    assert [f.subject for f in found] == ["pe_eth_tx.crc_state"]


def test_an_auto_named_dead_net_is_not_reported():
    module = make_module(
        "m",
        hdlname="m",
        netnames={"$abc$67326$new_n1627": make_net("$abc$67326$new_n1627", (5,))},
    )
    assert [f for f in detect(design_with(module)) if f.code == "dead-net"] == []


def test_a_constant_net_is_reported():
    module = make_module(
        "pe_ctrl",
        hdlname="pe_ctrl",
        netnames={"host_imem_sel": make_net("host_imem_sel", ("0",))},
    )
    found = [f for f in detect(design_with(module)) if f.code == "constant-net"]
    assert [f.subject for f in found] == ["pe_ctrl.host_imem_sel"]


def test_unused_sinks_and_function_locals_are_not_reported_as_constant_nets():
    module = make_module(
        "pe_ctrl",
        hdlname="pe_ctrl",
        netnames={
            "_unused_r2": make_net("_unused_r2", ("0",)),
            "crc16_byte$func$rtl/pe_ctrl.v:458$2247.crc": make_net(
                "crc16_byte$func$rtl/pe_ctrl.v:458$2247.crc", ("0",)
            ),
        },
    )
    assert [f for f in detect(design_with(module)) if f.code == "constant-net"] == []


def test_a_register_file_is_reported_from_array_shaped_net_names():
    cells: dict[str, Cell] = {}
    nets: dict[str, Net] = {}
    for i in range(8):
        cells[f"$auto$ff${i}"] = flop(f"$auto$ff${i}", q_bit=200 + i, d_bit=100 + i)
        cells[f"u_use{i}"] = reader(f"u_use{i}", 200 + i, 300 + i)
        nets[f"resp_buf[{i}]"] = make_net(f"resp_buf[{i}]", (200 + i,))
    module = make_module("pe_ctrl", hdlname="pe_ctrl", cells=cells, netnames=nets)
    found = [f for f in detect(design_with(module)) if f.code == "register-file"]
    assert len(found) == 1
    assert "resp_buf" in found[0].subject
    assert "8" in found[0].detail


def test_a_single_flop_is_not_a_register_file():
    cells = {"$auto$ff$0": flop("$auto$ff$0", 200, 100), "u_use0": reader("u_use0", 200, 300)}
    nets = {"resp_buf[0]": make_net("resp_buf[0]", (200,))}
    module = make_module("pe_ctrl", hdlname="pe_ctrl", cells=cells, netnames=nets)
    assert [f for f in detect(design_with(module)) if f.code == "register-file"] == []


def test_an_undriven_output_is_an_error_not_an_observation():
    module = make_module("m", hdlname="m", ports={"y": make_port("y", "output", (5,))})
    found = [f for f in detect(design_with(module)) if f.code == "undriven-output"]
    assert [f.subject for f in found] == ["m.y"]
    assert found[0].klass == "error"


def test_an_output_that_aliases_a_module_input_is_not_undriven():
    # `assign io_port = arg[3:0]`: no cell drives io_port and it is perfectly driven.
    # Getting this wrong produced 160 false positives on the reference design.
    module = make_module(
        "pe_cpu",
        hdlname="pe_cpu",
        ports={
            "arg": make_port("arg", "input", (17, 18)),
            "io_port": make_port("io_port", "output", (17, 18)),
        },
    )
    assert [f for f in detect(design_with(module)) if f.code == "undriven-output"] == []


def test_two_cells_driving_one_bit_is_an_error():
    cells = {
        "u_a": make_cell(
            "u_a",
            "sg13g2_nand2_1",
            connections={"A": (1,), "B": (2,), "Y": (9,)},
            port_directions={"Y": "output"},
        ),
        "u_b": make_cell(
            "u_b",
            "sg13g2_nand2_1",
            connections={"A": (3,), "B": (4,), "Y": (9,)},
            port_directions={"Y": "output"},
        ),
    }
    found = [
        f
        for f in detect(design_with(make_module("m", hdlname="m", cells=cells)))
        if f.code == "multiple-drivers"
    ]
    assert len(found) == 1
    assert found[0].klass == "error"


def test_observations_are_labelled_observations():
    module = make_module(
        "pe_dru",
        hdlname="pe_dru",
        cells={"u_la": latch()},
        netnames={"dead": make_net("dead", (9,))},
    )
    findings = detect(design_with(module))
    assert findings
    assert {f.klass for f in findings} == {"observation"}


def test_negative_results_are_mapped_only_and_never_claim_width_truncation():
    module = make_module("m", hdlname="m")
    mapped = negative_results(design_with(module))
    assert any("multiple drivers" in line for line in mapped)
    assert any("undriven" in line for line in mapped)
    assert not any("width truncation" in line for line in mapped)
    rtl_ish = make_design({module.name: module}, flavour="rtl-ish")
    assert negative_results(rtl_ish) == []


def test_findings_are_labelled_with_the_module_label_not_the_key():
    # The whole reason naming.py exists: a parameter-mangled module key must never
    # reach a reader. A dead net inside pe_ctrl should read `pe_ctrl.<net>`.
    module = make_module(
        "$paramod\\pe_ctrl\\WORDS=s32'00000000000000000000010000000000",
        hdlname="pe_ctrl",
        netnames={"crc_state": make_net("crc_state", (5, 6))},
    )
    found = [f for f in detect(design_with(module)) if f.code == "dead-net"]
    assert [f.subject for f in found] == ["pe_ctrl.crc_state"]


def test_every_finding_names_the_module_it_came_from():
    # The viewer filters findings by module key. A finding without that field is a
    # finding the page computes and then never shows.
    module = make_module(
        "$paramod\\pe_dru\\SPB=s32'00000000000000000000000000001100",
        hdlname="pe_dru",
        cells={"u_la": latch()},
        netnames={"dead": make_net("dead", (9,))},
    )
    design = make_design({module.name: replace(module, is_stub=False), **stubs()})
    found = detect(design)
    assert found
    for finding in found:
        assert finding.module == module.name, finding
