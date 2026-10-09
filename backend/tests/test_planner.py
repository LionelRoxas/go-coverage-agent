# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
from app.agents.planner import plan
from app.models import CoverageReport, FuncCoverage, FuncKey


def fc(file, name, statements, covered=0):
    return FuncCoverage(key=FuncKey(file=file, name=name), statements=statements, covered=covered)


def report(*fns):
    return CoverageReport(total_statements=0, covered_statements=0, percent=0, files=[], functions=list(fns), covered_block_ids=[])


def test_groups_by_file_ranked_by_uncovered():
    r = report(fc("a.go", "A1", 10), fc("b.go", "B1", 30), fc("a.go", "A2", 5), fc("c.go", "C1", 1, covered=1))
    items = plan(r, {}, set())
    assert [i.file for i in items] == ["b.go", "a.go"]
    assert [k.name for k in items[1].functions] == ["A1", "A2"]
    assert items[1].uncovered_statements == 15


def test_respects_max_items_and_statement_cap():
    r = report(fc("a.go", "A1", 50), fc("a.go", "A2", 20), fc("b.go", "B", 9), fc("c.go", "C", 8), fc("d.go", "D", 7))
    items = plan(r, {}, set(), max_items=3, max_statements=60)
    assert [i.file for i in items] == ["a.go", "b.go", "c.go"]
    assert [k.name for k in items[0].functions] == ["A1"]  # A2 would exceed 60


def test_first_function_always_included_even_if_over_cap():
    items = plan(report(fc("a.go", "Big", 200)), {}, set(), max_statements=60)
    assert items[0].functions[0].name == "Big"


def test_skips_failed_and_skipped():
    a, b = FuncKey(file="a.go", name="A"), FuncKey(file="b.go", name="B")
    r = report(fc("a.go", "A", 10), fc("b.go", "B", 9), fc("c.go", "C", 1))
    assert [i.file for i in plan(r, {a: 2}, {b})] == ["c.go"]
    assert [i.file for i in plan(r, {a: 1}, set())][0] == "a.go"


def test_empty_when_nothing_left():
    assert plan(report(fc("a.go", "A", 3, covered=3)), {}, set()) == []
