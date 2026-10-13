"""CLI tests.

The contract, in the spec's own words: `0` rendered, `1` `--check` found the page stale,
`2` cannot complete. Findings are content and never change the exit code — the reference
design has latches and dead nets by construction, so a nonzero exit for them would make
the command useless and would stop a gate from telling "stale" from "this design has
latches".
"""

from __future__ import annotations

import json

import pytest

from tests.factories import write_netlist
from verilog_explorer.cli import main


def test_help_exits_zero():
    with pytest.raises(SystemExit) as caught:
        main(["--help"])
    assert caught.value.code == 0


def test_a_netlist_renders_to_the_requested_file(tmp_path):
    netlist, _ = write_netlist(tmp_path)
    out = tmp_path / "ve.html"
    assert main([str(netlist), "-o", str(out)]) == 0
    assert out.is_file()
    assert "tt_um" in out.read_text(encoding="utf-8")


def test_the_output_defaults_next_to_the_netlist(tmp_path):
    netlist, _ = write_netlist(tmp_path)
    assert main([str(netlist)]) == 0
    assert (tmp_path / "netlist.html").is_file()


def test_check_is_clean_when_the_page_is_current(tmp_path, capsys):
    netlist, _ = write_netlist(tmp_path)
    out = tmp_path / "ve.html"
    assert main([str(netlist), "-o", str(out)]) == 0
    assert main([str(netlist), "-o", str(out), "--check"]) == 0
    assert "ok" in capsys.readouterr().out


def test_check_reports_stale_when_the_page_no_longer_matches(tmp_path, capsys):
    netlist, _ = write_netlist(tmp_path)
    out = tmp_path / "ve.html"
    assert main([str(netlist), "-o", str(out)]) == 0
    out.write_text("something else\n", encoding="utf-8")
    assert main([str(netlist), "-o", str(out), "--check"]) == 1
    assert "stale" in capsys.readouterr().out


def test_check_does_not_write(tmp_path):
    netlist, _ = write_netlist(tmp_path)
    out = tmp_path / "ve.html"
    out.write_text("untouched\n", encoding="utf-8")
    assert main([str(netlist), "-o", str(out), "--check"]) == 1
    assert out.read_text(encoding="utf-8") == "untouched\n"


def test_a_document_that_is_not_a_netlist_exits_two_with_a_sentence(tmp_path, capsys):
    bad = tmp_path / "not-a-netlist.json"
    bad.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
    assert main([str(bad), "-o", str(tmp_path / "ve.html")]) == 2
    assert "not a yosys JSON netlist" in capsys.readouterr().err


def test_a_missing_netlist_exits_two(tmp_path, capsys):
    assert main([str(tmp_path / "absent.json"), "-o", str(tmp_path / "ve.html")]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_a_source_root_that_resolves_nothing_exits_two(tmp_path, capsys):
    netlist, _ = write_netlist(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    assert main([str(netlist), "-o", str(tmp_path / "ve.html"), "--src-root", str(empty)]) == 2
    assert "no source file" in capsys.readouterr().err


def test_findings_do_not_change_the_exit_code(tmp_path):
    # The fixture netlist has a dead net by construction; it still renders, and exits 0.
    netlist, src_root = write_netlist(tmp_path)
    out = tmp_path / "ve.html"
    assert main([str(netlist), "-o", str(out), "--src-root", str(src_root)]) == 0
