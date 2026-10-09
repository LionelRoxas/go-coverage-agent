# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import json

import pytest

from app.llm.limits import RateLimiter, UsageLedger, parse_duration


@pytest.mark.parametrize("text,seconds", [("7.66s", 7.66), ("2m59.56s", 179.56), ("120ms", 0.12), ("1h2m3s", 3723.0), ("", 0.0)])
def test_parse_duration(text, seconds):
    assert parse_duration(text) == pytest.approx(seconds)


def test_rate_limiter_waits_until_reset_when_low():
    now = [100.0]
    rl = RateLimiter(clock=lambda: now[0])
    assert rl.wait_needed(7000) == 0.0  # nothing known yet
    rl.update({"x-ratelimit-remaining-tokens": "3000", "x-ratelimit-reset-tokens": "40s"})
    assert rl.wait_needed(2000) == 0.0
    assert rl.wait_needed(7000) == pytest.approx(40.0)
    now[0] = 150.0
    assert rl.wait_needed(7000) == 0.0  # reset passed


def test_ledger_tracks_per_day_and_survives_corruption(tmp_path):
    day = ["2026-10-08"]
    path = tmp_path / ".usage.json"
    ledger = UsageLedger(path, daily_budget=1000, today=lambda: day[0])
    ledger.add(300)
    assert ledger.remaining() == 700
    assert UsageLedger(path, 1000, today=lambda: day[0]).used_today() == 300
    day[0] = "2026-10-09"
    assert ledger.remaining() == 1000
    path.write_text("{not json")
    assert UsageLedger(path, 1000, today=lambda: day[0]).used_today() == 0
    ledger.add(10)
    assert json.loads(path.read_text())["2026-10-09"] == 10
