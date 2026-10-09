# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from app.agents.history import RECORD_CHARS, attempt_record, failure_lines, render_history
from app.llm.client import estimate_tokens
from app.validator import ValidationKind, ValidationResult

# go test -count=2 prints every failure twice (from output/7ef641efb870, iteration 7)
EVIDENCE = """--- FAIL: TestParseConstraint_UncoveredBranches (0.00s)
    --- FAIL: TestParseConstraint_UncoveredBranches/!=_1.x (0.00s)
        constraints_test.go:721: minorDirty = true, want false
    --- FAIL: TestParseConstraint_UncoveredBranches/!=_1.2.x (0.00s)
        constraints_test.go:721: minorDirty = false, want true
--- FAIL: TestConstraintNotEqual_UncoveredBranches (0.00s)
    constraints_test.go:772: expected error for minor dirty equality, got nil
--- FAIL: TestParseConstraint_UncoveredBranches (0.00s)
    --- FAIL: TestParseConstraint_UncoveredBranches/!=_1.x (0.00s)
        constraints_test.go:721: minorDirty = true, want false
    --- FAIL: TestParseConstraint_UncoveredBranches/!=_1.2.x (0.00s)
        constraints_test.go:721: minorDirty = false, want true
--- FAIL: TestConstraintNotEqual_UncoveredBranches (0.00s)
    constraints_test.go:772: expected error for minor dirty equality, got nil
FAIL
coverage: 92.8% of statements
FAIL\tgithub.com/Masterminds/semver/v3\t0.015s
FAIL"""
FAILED = ["TestParseConstraint_UncoveredBranches", "TestConstraintNotEqual_UncoveredBranches"]
NO_GAIN = ValidationResult(ValidationKind.NO_GAIN, "the new tests executed no previously uncovered statements")


def test_failure_lines_keep_each_assertion_once_with_its_subtest():
    assert failure_lines(EVIDENCE) == [
        "TestParseConstraint_UncoveredBranches/!=_1.x: constraints_test.go:721: minorDirty = true, want false",
        "TestParseConstraint_UncoveredBranches/!=_1.2.x: constraints_test.go:721: minorDirty = false, want true",
        "TestConstraintNotEqual_UncoveredBranches: constraints_test.go:772: expected error for minor dirty equality, got nil",
    ]


def test_failure_lines_cap_each_failing_test():
    out = "--- FAIL: TestX (0.00s)\n" + "".join(
        f"    --- FAIL: TestX/c{i} (0.00s)\n        x_test.go:{i}: got {i} want 0\n" for i in range(10))
    lines = failure_lines(out)
    assert len(lines) == 3 and lines[0] == "TestX/c0: x_test.go:0: got 0 want 0"


def test_failure_lines_keep_panics():
    out = "--- FAIL: TestX (0.00s)\npanic: runtime error: index out of range [3] with length 3 [recovered]\n\tpanic: x\n"
    assert failure_lines(out)[0] == "TestX: panic: runtime error: index out of range [3] with length 3 [recovered]"


def test_records_by_kind():
    failing = attempt_record("writer", ValidationResult(ValidationKind.TEST_FAILURE, EVIDENCE, failed_tests=FAILED))
    assert failing.observed and failing.failed_tests == tuple(FAILED) and len(failing.lines) == 3
    compile_ = attempt_record("llm_fix 1", ValidationResult(
        ValidationKind.COMPILE_ERROR, "# m\n./a_test.go:3:2: undefined: foo\n./a_test.go:4:2: undefined: bar\n"
        "./a_test.go:5:2: undefined: baz\n./a_test.go:6:2: undefined: qux\n"))
    assert compile_.lines == ("./a_test.go:3:2: undefined: foo", "./a_test.go:4:2: undefined: bar",
                              "./a_test.go:5:2: undefined: baz") and not compile_.observed
    pruned = attempt_record("prune of [TestA]", NO_GAIN, pruned=["TestA"])
    assert pruned.lines == ("the new tests executed no previously uncovered statements",)
    assert pruned.pruned == ("TestA",)


def test_each_record_renders_within_its_cap():
    long = "--- FAIL: TestX (0.00s)\n" + "".join(
        f"    --- FAIL: TestX/c{i} (0.00s)\n        x_test.go:{i}: {'y' * 300}\n" for i in range(3))
    rec = attempt_record("auto_fix: " + "z" * 600, ValidationResult(ValidationKind.TEST_FAILURE, long, failed_tests=["TestX"]))
    text = rec.render(1)
    assert len(text) <= RECORD_CHARS and text.startswith("1. auto_fix: ")


def test_history_renders_oldest_first_and_drops_middle_records_over_the_cap():
    first = attempt_record("writer", ValidationResult(ValidationKind.TEST_FAILURE, EVIDENCE, failed_tests=FAILED))
    noise = [attempt_record(f"llm_fix {i}", ValidationResult(ValidationKind.VET_ERROR, f"vet: {'n' * 300} {i}"))
             for i in range(1, 30)]
    last = attempt_record("llm_fix 30", ValidationResult(
        ValidationKind.TEST_FAILURE, "--- FAIL: TestY (0.00s)\n    y_test.go:9: got 7 want 8\n", failed_tests=["TestY"]))
    text = render_history([first, *noise, last], max_tokens=300)
    assert estimate_tokens(text) <= 300
    assert text.index("minorDirty = true, want false") < text.index("got 7 want 8")
    assert "1. writer" in text and "31. llm_fix 30" in text and "2. llm_fix 1" not in text
    assert "omitted" in text


def test_empty_history_renders_nothing():
    assert render_history([], max_tokens=1500) == ""
