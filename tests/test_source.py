"""Source-resolution tests.

Two failure modes decide this module's contract, and both are about not lying:

* A `src` value is a path relative to the directory synthesis ran in, so it must
  resolve as `src_root / src_path` exactly. A basename match would find *a*
  `pe_ctrl.v` and link to the wrong one, which is worse than no link at all.
* A `src` range can outlive the file it points at. Six `.ys` snapshots in the
  reference design's review directories no longer match the tree they described,
  which is the failure this tool exists to prevent — so a range that runs past the
  end of the file says so.
"""

from __future__ import annotations

from verilog_explorer.source import SourceIndex, parse_src


def test_parse_src_reads_file_and_range():
    assert parse_src("rtl/pe_ctrl.v:636.3-1326.6") == ("rtl/pe_ctrl.v", 636, 1326)


def test_parse_src_rejects_a_path_with_no_range():
    assert parse_src("rtl/pe_ctrl.v") is None


def test_parse_src_rejects_a_single_position():
    assert parse_src("rtl/pe_ctrl.v:10.1") is None


def test_parse_src_rejects_nonsense():
    assert parse_src("nonsense") is None
    assert parse_src("") is None


def test_parse_src_tolerates_surrounding_whitespace():
    # Real `src` values arrive out of the file with no stray space; say so either way.
    assert parse_src("  rtl/pe_ctrl.v:1.1-2.1\n") == ("rtl/pe_ctrl.v", 1, 2)


def test_locate_resolves_against_the_synthesis_root(tmp_path):
    target = tmp_path / "rtl" / "pe_ctrl.v"
    target.parent.mkdir(parents=True)
    target.write_text("a\nb\nc\n", encoding="utf-8")
    ix = SourceIndex(tmp_path)
    loc = ix.locate("rtl/pe_ctrl.v:1.1-2.1")
    assert loc is not None
    assert loc.path == target
    assert (loc.first_line, loc.last_line) == (1, 2)


def test_locate_does_not_match_by_basename(tmp_path):
    target = tmp_path / "rtl" / "pe_ctrl.v"
    target.parent.mkdir(parents=True)
    target.write_text("a\n", encoding="utf-8")
    ix = SourceIndex(tmp_path)
    assert ix.locate("elsewhere/pe_ctrl.v:1.1-1.2") is None


def test_locate_returns_none_for_a_missing_file_without_raising(tmp_path):
    assert SourceIndex(tmp_path).locate("rtl/absent.v:1.1-2.1") is None


def test_a_source_index_with_no_root_never_raises():
    ix = SourceIndex(None)
    assert ix.locate("rtl/pe_ctrl.v:1.1-2.1") is None
    assert ix.drift("rtl/pe_ctrl.v:1.1-2.1") is None


def test_drift_is_silent_when_the_range_fits(tmp_path):
    target = tmp_path / "rtl" / "pe_ctrl.v"
    target.parent.mkdir(parents=True)
    target.write_text("a\nb\nc\n", encoding="utf-8")
    assert SourceIndex(tmp_path).drift("rtl/pe_ctrl.v:1.1-3.1") is None


def test_a_range_past_the_end_of_the_file_is_reported_as_drift(tmp_path):
    target = tmp_path / "rtl" / "pe_ctrl.v"
    target.parent.mkdir(parents=True)
    target.write_text("a\nb\nc\n", encoding="utf-8")
    message = SourceIndex(tmp_path).drift("rtl/pe_ctrl.v:636.3-1326.6")
    assert message is not None
    assert "not the revision" in message


def test_an_unparseable_src_is_not_drift(tmp_path):
    assert SourceIndex(tmp_path).drift("nonsense") is None


def test_lines_are_read_once(tmp_path):
    target = tmp_path / "rtl" / "a.v"
    target.parent.mkdir(parents=True)
    target.write_text("one\ntwo\n", encoding="utf-8")
    ix = SourceIndex(tmp_path)
    assert ix.lines(target) == ["one", "two"]
    target.write_text("changed\n", encoding="utf-8")
    assert ix.lines(target) == ["one", "two"]


def test_lines_returns_none_for_a_missing_file(tmp_path):
    assert SourceIndex(tmp_path).lines(tmp_path / "absent.v") is None
