"""Renderer tests.

The page is the product, so these assert the things a reader would notice were missing:
the design's name and its counts, which netlist flavour the numbers describe, the
findings, and the model itself as JSON (the page is data plus a small viewer, not a
server).
"""

from __future__ import annotations

import json
import re

from tests.factories import make_cell, make_design, make_module, make_net, write_netlist
from verilog_explorer.load import load_design
from verilog_explorer.render import render_html
from verilog_explorer.source import SourceIndex

MODEL_BLOCK = re.compile(
    r'<script id="ve-model" type="application/json">(?P<body>.*?)</script>', re.DOTALL
)


def test_the_page_names_the_design_and_its_cells(tmp_path):
    netlist, _ = write_netlist(tmp_path)
    page = render_html(load_design(netlist))
    assert "tt_um" in page
    # tt_um holds one instance; pe_child holds one flop. Two cells over two modules.
    assert "2" in page
    assert page.lstrip().startswith("<!DOCTYPE html>")


def test_the_model_is_embedded_as_json(tmp_path):
    netlist, _ = write_netlist(tmp_path)
    page = render_html(load_design(netlist))
    match = MODEL_BLOCK.search(page)
    assert match is not None
    model = json.loads(match.group("body"))
    assert {m["label"] for m in model["modules"]} == {"pe_child", "tt_um"}


def test_the_page_states_which_netlist_flavour_the_numbers_describe(tmp_path):
    netlist, _ = write_netlist(tmp_path)
    assert "mapped" in render_html(load_design(netlist))


def test_findings_appear_with_their_subject(tmp_path):
    netlist, _ = write_netlist(tmp_path)
    design = load_design(netlist)
    page = render_html(design)
    assert "no multiple drivers" in page
    assert "no undriven outputs" in page


def test_a_dead_net_finding_reaches_the_page():
    module = make_module(
        "pe_eth_tx",
        hdlname="pe_eth_tx",
        cells={"u_g": make_cell("u_g", "sg13g2_inv_1")},
        netnames={"crc_state": make_net("crc_state", (5, 6))},
    )
    design = make_design({module.name: module, "sg13g2_inv_1": make_module("sg13g2_inv_1")})
    page = render_html(design)
    assert "crc_state" in page
    assert "no cell in this module reads it" in page


def test_source_ranges_are_carried_when_a_source_root_is_given(tmp_path):
    netlist, src_root = write_netlist(tmp_path)
    page = render_html(load_design(netlist), sources=SourceIndex(src_root))
    assert "pe_child.v" in page


def test_an_empty_design_still_renders():
    page = render_html(make_design({}))
    assert page.lstrip().startswith("<!DOCTYPE html>")
    assert "no design modules" in page.lower()


def test_the_page_needs_no_network():
    netlist_free = render_html(make_design({}))
    for forbidden in ("http://", "https://", "cdn.", "<link rel=", 'src="http'):
        assert forbidden not in netlist_free
