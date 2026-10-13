"""Naming tests: the design's own words, not the tool's.

Every expectation here is a real string taken from the reference design, because
the names are the whole difficulty: `$paramod\\pe_ctrl\\WORDS=s32'0…100`,
`$abc$67326$new_n1627`, `$auto$ff.cc:337:slice$28794`.
"""

from __future__ import annotations

from tests.factories import make_module, make_net
from verilog_explorer.naming import (
    format_bits,
    is_auto_name,
    module_label,
    net_label,
    parameter_badges,
)


def test_module_label_prefers_hdlname():
    m = make_module(
        name="$paramod\\pe_ctrl\\WORDS=s32'00000000000000000000010000000000",
        hdlname="pe_ctrl",
    )
    assert module_label(m) == "pe_ctrl"


def test_module_label_falls_back_to_strip_without_hdlname():
    m = make_module(name="$paramod$7f9518eacb819f12609a81d25055eeb8d348b0ad\\pe_soc")
    assert module_label(m) == "pe_soc"


def test_module_label_leaves_a_plain_name_alone():
    assert module_label(make_module(name="pe_serdes", hdlname="pe_serdes")) == "pe_serdes"


def test_parameter_badges_decode_a_binary_s32():
    m = make_module(
        name="$paramod\\pe_ctrl\\WORDS=s32'00000000000000000000010000000000",
        hdlname="pe_ctrl",
    )
    assert parameter_badges(m) == ["WORDS=1024"]


def test_parameter_badges_keep_an_unparseable_value_verbatim():
    m = make_module(name="$paramod\\pe_dru\\SPB=hello", hdlname="pe_dru")
    assert parameter_badges(m) == ["SPB=hello"]


def test_bits_render_as_a_range_only_when_contiguous():
    assert format_bits((0, 1, 2, 3)) == "3:0"


def test_bits_that_are_not_contiguous_say_how_wide_they_are():
    bits = (39, 42, 14, 15, 16, 17, 80, 81, 82, 83)
    assert format_bits(bits) == "10 bits"


def test_a_single_bit_renders_as_its_index():
    assert format_bits((340,)) == "340"


def test_a_constant_bit_renders_as_the_constant():
    assert format_bits(("0",)) == "0"


def test_auto_names_are_detected():
    assert is_auto_name("$abc$67326$new_n1627")
    assert is_auto_name("$auto$ff.cc:337:slice$28794")
    assert is_auto_name("$0\\rstate[2:0]")
    assert is_auto_name("_unused_r2")
    assert not is_auto_name("resp_buf")
    assert not is_auto_name("clk")


def test_net_label_prefers_the_human_name_for_a_bit():
    m = make_module(
        name="pe_ctrl",
        hdlname="pe_ctrl",
        netnames={
            "clk": make_net("clk", (7,)),
            "$abc$1$new_n5": make_net("$abc$1$new_n5", (7,)),
        },
    )
    assert net_label(m, 7) == "clk"


def test_net_label_falls_back_to_an_auto_name_when_that_is_all_there_is():
    m = make_module(
        name="pe_ctrl",
        hdlname="pe_ctrl",
        netnames={"$abc$1$new_n5": make_net("$abc$1$new_n5", (9,))},
    )
    assert net_label(m, 9) == "$abc$1$new_n5"


def test_net_label_names_a_bit_that_has_no_name_at_all():
    assert net_label(make_module(name="m"), 11) == "bit 11"


def test_net_label_ignores_hidden_names():
    m = make_module(
        name="m",
        hdlname="m",
        netnames={
            "hidden": make_net("hidden", (4,), hide_name=True),
            "shown": make_net("shown", (4,)),
        },
    )
    assert net_label(m, 4) == "shown"
