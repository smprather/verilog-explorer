"""Loader tests: yosys JSON -> model.

The fixture below is the smallest document that still has the shapes that bit us:
a design module, a stub for a library cell, a stub for a blackbox macro, a cell
carrying `src`, and a connection list holding a bit index.
"""

from __future__ import annotations

import json

import pytest

from verilog_explorer.load import NotANetlistError, load_design
from verilog_explorer.model import is_const

NETLIST = {
    "creator": "Yosys 0.69",
    "modules": {
        "top": {
            "attributes": {"top": "00000000000000000000000000000001"},
            "ports": {
                "a": {"direction": "input", "bits": [2]},
                "y": {"direction": "output", "bits": [3]},
            },
            "cells": {
                "u_sub": {
                    "hide_name": 0,
                    "type": "sub",
                    "port_directions": {"a": "input", "y": "output"},
                    "connections": {"a": [2], "y": [3]},
                    "parameters": {},
                    "attributes": {"src": "t.v:3.1-3.9"},
                }
            },
            "netnames": {"a": {"hide_name": 0, "bits": [2]}},
        },
        "sub": {
            "attributes": {"hdlname": "sub"},
            "ports": {"a": {"direction": "input", "bits": [0]}},
            "cells": {},
            "netnames": {},
        },
        "sg13g2_nand2_1": {
            "attributes": {},
            "ports": {"A": {"direction": "input", "bits": [0]}},
            "cells": {},
            "netnames": {},
        },
        "RM_IHPSG13_1P_1024x16_c2_bm_bist": {
            "attributes": {"blackbox": "00"},
            "ports": {},
            "cells": {},
            "netnames": {},
        },
    },
}


def write_netlist(tmp_path, doc=NETLIST):
    p = tmp_path / "n.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def test_stub_is_a_module_with_no_cells(tmp_path):
    d = load_design(write_netlist(tmp_path))
    assert d.modules["top"].is_stub is False
    assert d.modules["sg13g2_nand2_1"].is_stub is True
    assert d.modules["sub"].is_stub is True


def test_bit_indices_keep_their_type(tmp_path):
    # yosys writes indices as JSON numbers and constants as JSON strings. If this
    # normalised both to strings, bit 0 of every bus would read as the constant 0.
    d = load_design(write_netlist(tmp_path))
    assert d.modules["top"].cells["u_sub"].connections["a"] == (2,)


def test_constants_are_recognised():
    assert is_const("0")
    assert is_const("x")
    assert not is_const(0)
    assert not is_const(12)


def test_flavour_is_mapped_when_a_mapped_cell_appears(tmp_path):
    doc = json.loads(json.dumps(NETLIST))
    doc["modules"]["top"]["cells"]["u_g1"] = {
        "hide_name": 0,
        "type": "sg13g2_nand2_1",
        "port_directions": {"A": "input", "B": "input", "Y": "output"},
        "connections": {"A": [2], "B": [2], "Y": [3]},
        "parameters": {},
        "attributes": {},
    }
    assert load_design(write_netlist(tmp_path, doc)).flavour == "mapped"


def test_flavour_is_rtlish_when_only_operator_cells_appear(tmp_path):
    # The liberty stubs are loaded before `proc` and so appear in both flavours;
    # they must not be what decides.
    doc = json.loads(json.dumps(NETLIST))
    doc["modules"]["top"]["cells"]["u_sub"]["type"] = "$add"
    doc["modules"].pop("sg13g2_nand2_1", None)
    doc["modules"].pop("RM_IHPSG13_1P_1024x16_c2_bm_bist", None)
    assert load_design(write_netlist(tmp_path, doc)).flavour == "rtl-ish"


def test_flavour_is_unknown_with_neither_vocabulary(tmp_path):
    doc = json.loads(json.dumps(NETLIST))
    doc["modules"].pop("sg13g2_nand2_1", None)
    doc["modules"].pop("RM_IHPSG13_1P_1024x16_c2_bm_bist", None)
    assert load_design(write_netlist(tmp_path, doc)).flavour == "unknown"


def test_top_is_taken_from_the_top_attribute(tmp_path):
    assert load_design(write_netlist(tmp_path)).top == "top"


def test_src_is_carried_through(tmp_path):
    d = load_design(write_netlist(tmp_path))
    assert d.modules["top"].cells["u_sub"].src == "t.v:3.1-3.9"


def test_a_document_that_is_not_a_netlist_is_rejected(tmp_path):
    p = tmp_path / "not-a-netlist.json"
    p.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
    with pytest.raises(NotANetlistError):
        load_design(p)


def test_a_missing_file_is_rejected(tmp_path):
    with pytest.raises(NotANetlistError):
        load_design(tmp_path / "absent.json")
