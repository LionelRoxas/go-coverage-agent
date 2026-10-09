# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
from app.models import Block, CoverageReport, FuncKey, JobRequest, TokenUsage


def test_funckey_label_and_hashable():
    plain = FuncKey(file="mean.go", name="Mean")
    method = FuncKey(file="data.go", receiver="Float64Data", name="Mean")
    assert plain.label() == "Mean"
    assert method.label() == "Float64Data.Mean"
    assert len({plain, method, FuncKey(file="mean.go", name="Mean")}) == 2


def test_block_id_is_stable():
    b = Block(file="mean.go", start_line=3, start_col=2, end_line=5, end_col=10, statements=2)
    assert b.id == "mean.go:3.2,5.10"


def test_report_public_omits_block_ids():
    r = CoverageReport(total_statements=4, covered_statements=1, percent=25.0,
                       files=[], functions=[], covered_block_ids=["a"])
    assert r.covered_set() == frozenset({"a"})
    assert "covered_block_ids" not in r.public()


def test_job_request_defaults_and_bounds():
    req = JobRequest(repo_path="stats")
    assert req.target_coverage == 80
    assert req.options.max_iterations == 10
    assert req.options.exclude_patterns == ["examples/**", "testdata/**"]


def test_token_usage_add():
    total = TokenUsage(prompt_tokens=10, completion_tokens=5).add(TokenUsage(prompt_tokens=1, completion_tokens=1))
    assert total.total == 17
