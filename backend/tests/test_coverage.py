# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import pytest

from app.coverage import parse_profile, summarize
from app.models import FuncInfo, FuncKey

PROFILE = """mode: set
example.com/m/a.go:3.20,5.2 1 1
example.com/m/a.go:5.2,7.3 2 0
example.com/m/a.go:9.30,11.2 1 0
example.com/m/sub/b.go:1.1,2.2 3 1
example.com/m/a.go:3.20,5.2 1 0
"""

FUNCS = [
    FuncInfo(key=FuncKey(file="a.go", name="Abs"), package="m", start_line=3, end_line=8, exported=True),
    FuncInfo(key=FuncKey(file="a.go", receiver="T", name="Mean"), package="m", start_line=9, end_line=11, exported=True),
    FuncInfo(key=FuncKey(file="sub/b.go", name="B"), package="sub", start_line=1, end_line=2, exported=True),
]


def test_parse_profile_strips_module_and_or_merges_duplicates():
    hits = parse_profile(PROFILE, "example.com/m")
    assert len(hits) == 4
    by_id = {b.id: h for b, h in hits.items()}
    assert by_id["a.go:3.20,5.2"] is True  # one run hit it, the duplicate did not
    assert by_id["sub/b.go:1.1,2.2"] is True
    assert by_id["a.go:5.2,7.3"] is False


def test_parse_profile_rejects_garbage():
    with pytest.raises(ValueError, match="unrecognized coverage line"):
        parse_profile("mode: set\nnot a profile line\n", "example.com/m")


def test_parse_profile_empty_is_empty():
    assert parse_profile("mode: set\n", "example.com/m") == {}


def test_summarize_totals_files_and_functions():
    report = summarize(parse_profile(PROFILE, "example.com/m"), FUNCS)
    assert (report.total_statements, report.covered_statements) == (7, 4)
    assert report.percent == 57.14
    files = {f.file: f for f in report.files}
    assert (files["a.go"].statements, files["a.go"].covered, files["a.go"].percent) == (4, 1, 25.0)
    assert files["sub/b.go"].percent == 100.0

    fns = {f.key.label(): f for f in report.functions}
    assert (fns["Abs"].statements, fns["Abs"].covered) == (3, 1)
    assert fns["Abs"].uncovered_lines == [(5, 7)]
    assert fns["T.Mean"].uncovered_lines == [(9, 11)]
    assert fns["B"].uncovered_lines == []
    assert sorted(report.covered_block_ids) == ["a.go:3.20,5.2", "sub/b.go:1.1,2.2"]


def test_summarize_merges_adjacent_uncovered_ranges():
    profile = "mode: set\nm/a.go:3.1,4.2 1 0\nm/a.go:4.2,6.1 1 0\nm/a.go:8.1,8.9 1 0\n"
    funcs = [FuncInfo(key=FuncKey(file="a.go", name="F"), package="m", start_line=1, end_line=9, exported=True)]
    report = summarize(parse_profile(profile, "m"), funcs)
    assert report.functions[0].uncovered_lines == [(3, 6), (8, 8)]


def test_summarize_zero_statements_is_zero_percent():
    report = summarize({}, [])
    assert report.percent == 0.0 and report.files == [] and report.functions == []
