"""Net index tests: drivers, loads, and the boundary of a module.

WHY THIS EXISTS. Every one of these assertions encodes a mistake that was actually
made. The first measurement of the reference design reported 160 undriven outputs,
and all 160 were healthy: `assign io_port = arg[3:0]` leaves a port sharing a bit
index with the net it aliases, with no cell driving it anywhere. A second attempt
fixed the port *directions* and still flagged three, because a module's own input
port is a source at its boundary.
"""

from __future__ import annotations

from tests.factories import make_cell, make_design, make_module, make_net, make_port
from verilog_explorer.nets import NetIndex


def test_a_port_that_aliases_a_module_input_is_not_undriven():
    # pe_cpu.io_port is `assign io_port = arg[3:0]`: the bits are the input port's
    # bits and no cell drives them.
    m = make_module(
        "pe_cpu",
        ports={
            "arg": make_port("arg", "input", (17, 18, 19, 20)),
            "io_port": make_port("io_port", "output", (17, 18, 19, 20)),
        },
    )
    ix = NetIndex(m)
    assert ix.boundary(17) == "port:arg"
    assert ix.drivers(17) == ()


def test_a_load_is_a_cell_input_port_on_that_bit():
    cell = make_cell(
        "u_g",
        "sg13g2_nand2_1",
        connections={"A": (7,), "B": (8,), "Y": (9,)},
        port_directions={"A": "input", "B": "input", "Y": "output"},
    )
    ix = NetIndex(make_module("m", cells={"u_g": cell}))
    assert ix.loads(7) == (cell,)
    assert ix.loads(9) == ()


def test_drivers_are_cell_output_bits():
    cell = make_cell(
        "u_g",
        "sg13g2_nand2_1",
        connections={"A": (7,), "B": (8,), "Y": (9,)},
        port_directions={"A": "input", "B": "input", "Y": "output"},
    )
    ix = NetIndex(make_module("m", cells={"u_g": cell}))
    assert ix.drivers(9) == (cell,)


def test_constant_bits_are_driven_by_definition():
    ix = NetIndex(make_module("m"))
    assert ix.boundary("0") == "const"
    assert ix.boundary("1") == "const"


def test_an_index_and_a_constant_never_collide():
    # Index 0 and the constant "0" are different bits. Stringifying both — the
    # obvious simplification — makes the two lookups below return each other's cells.
    on_index = make_cell(
        "u_a",
        "sg13g2_nand2_1",
        connections={"A": (0,)},
        port_directions={"A": "input"},
    )
    on_const = make_cell(
        "u_b",
        "sg13g2_nand2_1",
        connections={"A": ("0",)},
        port_directions={"A": "input"},
    )
    ix = NetIndex(make_module("m", cells={"u_a": on_index, "u_b": on_const}))
    assert ix.loads(0) == (on_index,)
    assert ix.loads("0") == (on_const,)
    assert ix.boundary(0) is None
    assert ix.boundary("0") == "const"


def test_a_module_output_port_bit_counts_as_a_load():
    # Otherwise every output of every module looks like a dead net.
    m = make_module(
        "m",
        ports={"y": make_port("y", "output", (5,))},
        netnames={"y": make_net("y", (5,))},
    )
    assert NetIndex(m).dead_nets() == ()


def test_a_named_net_with_no_loads_is_dead():
    m = make_module(
        "pe_eth_tx",
        netnames={
            "crc_state": make_net("crc_state", (1, 2)),
            "used": make_net("used", (3,)),
        },
        cells={
            "u_g": make_cell(
                "u_g",
                "sg13g2_nand2_1",
                connections={"A": (3,), "B": (3,), "Y": (4,)},
                port_directions={"A": "input", "B": "input", "Y": "output"},
            )
        },
    )
    assert [n.name for n in NetIndex(m).dead_nets()] == ["crc_state"]


def test_a_dead_net_must_be_dead_on_every_bit():
    m = make_module(
        "m",
        netnames={"half": make_net("half", (1, 2))},
        cells={
            "u_g": make_cell(
                "u_g",
                "sg13g2_nand2_1",
                connections={"A": (2,), "B": (2,), "Y": (4,)},
                port_directions={"A": "input", "B": "input", "Y": "output"},
            )
        },
    )
    assert NetIndex(m).dead_nets() == ()


def test_a_hidden_net_is_not_reported_dead():
    m = make_module(
        "m",
        netnames={"$abc$1$new_n5": make_net("$abc$1$new_n5", (1,), hide_name=True)},
    )
    assert NetIndex(m).dead_nets() == ()


def test_parent_hint_names_the_instance_port():
    design = make_design(
        {
            "tt_um": make_module(
                "tt_um",
                hdlname="tt_um",
                is_top=True,
                cells={
                    "u_soc": make_cell(
                        "u_soc",
                        "pe_soc",
                        connections={"imem_addr": (1,), "imem_rdata": (2,)},
                        port_directions={"imem_addr": "output", "imem_rdata": "input"},
                    )
                },
            ),
            "pe_soc": make_module("pe_soc", hdlname="pe_soc", cells={"u_g": make_cell("u_g")}),
        }
    )
    ix = NetIndex(design.modules["pe_soc"], design)
    assert ix.parent_hint("imem_addr") == "u_soc.imem_addr"


def test_parent_hint_is_none_when_nothing_instantiates_the_module():
    design = make_design(
        {"pe_soc": make_module("pe_soc", hdlname="pe_soc", cells={"u_g": make_cell("u_g")})}
    )
    ix = NetIndex(design.modules["pe_soc"], design)
    assert ix.parent_hint("imem_addr") is None
