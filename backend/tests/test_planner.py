# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
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


def test_ranks_files_by_packed_total_not_biggest_function():
    r = report(fc("a.go", "A", 30), fc("b.go", "B1", 25), fc("b.go", "B2", 25), fc("b.go", "B3", 25))
    items = plan(r, {}, set(), max_items=2, max_statements=100)
    assert [i.file for i in items] == ["b.go", "a.go"]
    assert items[0].uncovered_statements == 75


def test_default_cap_packs_up_to_100_statements():
    r = report(fc("a.go", "A1", 60), fc("a.go", "A2", 30), fc("a.go", "A3", 20))
    item = plan(r, {}, set())[0]
    assert [k.name for k in item.functions] == ["A1", "A2"] and item.uncovered_statements == 90


def test_item_never_exceeds_max_functions_and_rest_is_planned_later():
    fns = [fc("data.go", f"F{i:02d}", 1) for i in range(36)]
    r = report(*fns)
    items = plan(r, {}, set())
    assert len(items) == 1 and len(items[0].functions) == 5
    assert [k.name for k in items[0].functions] == [f"F{i:02d}" for i in range(5)]  # deterministic order
    done = set(items[0].functions)
    later = plan(r, {}, done)
    assert len(later[0].functions) == 5 and not done & set(later[0].functions)


def test_max_functions_is_configurable():
    r = report(*[fc("a.go", f"F{i}", 1) for i in range(5)])
    assert len(plan(r, {}, set(), max_functions=2)[0].functions) == 2


def test_file_with_seven_uncovered_functions_yields_first_target_of_at_most_five():
    r = report(*[fc("a.go", f"F{i}", 1) for i in range(7)])
    items = plan(r, {}, set())
    assert len(items[0].functions) <= 5


def test_never_two_items_for_the_same_file_in_one_round():
    """PARALLEL_WRITERS relies on it: a round's writers never share a test file (one item per source file), for
    every targets_per_iteration up to 5, including after earlier splits (functions skipped as too large, or failed)
    send the rest of a file back to the pool."""
    import random
    rng = random.Random(51)
    files = [f"pkg/f{i}.go" for i in range(7)]
    for _ in range(300):
        fns = [fc(rng.choice(files), f"F{n}", rng.randint(1, 80), covered=rng.choice([0, 0, 1])) for n in range(25)]
        keys = [f.key for f in fns]
        skipped = set(rng.sample(keys, rng.randint(0, 8)))  # single functions skipped after a too-large answer
        failed = {k: rng.randint(0, 2) for k in rng.sample(keys, rng.randint(0, 8))}
        for max_items in range(1, 6):
            items = plan(report(*fns), failed, skipped, max_items=max_items)
            assert len({i.file for i in items}) == len(items) <= max_items
            assert all(k.file == i.file for i in items for k in i.functions)
