# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from app.engine.policy import StopPolicy, stop_message
from app.models import JobRequest, StopReason


def test_target_and_marginal():
    p = StopPolicy(target=80, min_gain=1.0, patience=2)
    assert p.target_reached(80.0) and not p.target_reached(79.99)
    assert not p.marginal([0.5])
    assert not p.marginal([0.5, 3.0])
    assert p.marginal([5.0, 0.2, 0.9])


def test_messages_are_plain_language():
    req = JobRequest(repo_path="stats", target_coverage=80)
    assert stop_message(StopReason.TARGET_REACHED, req) == "Reached the 80% coverage target."
    assert "2 iterations" in stop_message(StopReason.MARGINAL_GAINS, req)
    assert stop_message(StopReason.BUDGET_EXHAUSTED, req, "daily cap").endswith("daily cap")
