# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
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


def test_requests_in_flight_count_against_the_known_headroom():
    rl = RateLimiter(clock=lambda: 100.0)
    rl.update({"x-ratelimit-remaining-tokens": "30000", "x-ratelimit-reset-tokens": "40s"})
    rl.begin(16000)  # one request sent, not answered yet
    assert rl.wait_needed(16000) == pytest.approx(40.0)  # 30 000 - 16 000 in flight < 16 000
    rl.end(16000)
    assert rl.wait_needed(16000) == 0.0


def test_a_429_pauses_every_caller_until_its_retry_after():
    now = [100.0]
    rl = RateLimiter(clock=lambda: now[0])
    until = rl.pause(12)
    assert rl.probing and rl.paused() and rl.wait_needed(1) == pytest.approx(12.0)
    later = rl.pause(20)  # a second 429 extends the pause; the first caller's resume must not end it
    rl.resume(until)
    assert rl.wait_needed(1) == pytest.approx(20.0)
    rl.resume(later)
    assert not rl.paused() and rl.wait_needed(1) == 0.0
    assert rl.probing  # still one request at a time until one succeeds
    rl.recovered()
    assert not rl.probing


def test_ledger_reservations_are_checked_and_taken_in_one_step(tmp_path):
    ledger = UsageLedger(tmp_path / ".usage.json", daily_budget=40_000, today=lambda: "2026-10-09")
    assert ledger.try_reserve(16_000) and ledger.try_reserve(16_000)
    assert not ledger.try_reserve(16_000)  # 40 000 - 32 000 reserved < 16 000
    ledger.release(16_000)
    assert ledger.try_reserve(16_000)
