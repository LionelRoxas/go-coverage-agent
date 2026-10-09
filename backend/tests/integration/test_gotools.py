# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import asyncio
import os
import time

import pytest

from app.coverage import parse_profile, summarize
from app.config import Settings
from app.gotools import go_env, read_module_info, run

pytestmark = pytest.mark.integration


async def test_list_packages_excludes_main_and_examples(make_ws, tools_for):
    ws = make_ws()
    pkgs = await tools_for(ws).list_packages(["examples/**", "testdata/**"])
    assert [(p.rel_dir, p.name) for p in pkgs] == [(".", "calc")]


async def test_funcs_and_seeded_baseline_is_zero_with_full_denominator(make_ws, tools_for):
    ws = make_ws()
    tools = tools_for(ws)
    pkgs = await tools.list_packages(["examples/**"])
    ws.seed_packages([(p.rel_dir, p.name) for p in pkgs])
    profile = ws.scratch / "cover.out"
    r = await tools.test(pkgs, profile)
    assert r.exit_code == 0, r.combined
    module, _ = read_module_info(ws.root)
    report = summarize(parse_profile(profile.read_text(), module), await tools.funcs())
    assert report.total_statements > 0
    assert report.percent == 0.0
    assert {f.key.label() for f in report.functions} == {"Abs", "Sqrt"}


async def test_decls_merge_prune_roundtrip(make_ws, tools_for):
    ws = make_ws()
    tools = tools_for(ws)
    snippet = ws.scratch / "snippet.go"
    snippet.write_text('package calc\n\nimport "testing"\n\nfunc TestAbs(t *testing.T) {\n\tif Abs(-2) != 2 {\n\t\tt.Fatal("bad")\n\t}\n}\n')
    assert (await tools.merge("calc_test.go", snippet)).exit_code == 0
    assert await tools.decls(".") == ["TestAbs"]
    assert (await tools.prune("calc_test.go", ["TestAbs"])).exit_code == 0
    assert await tools.decls(".") == []


async def test_run_timeout_kills_whole_process_group(tmp_path):
    started = time.monotonic()
    r = await run(["sh", "-c", "sleep 30 & sleep 30"], cwd=tmp_path, timeout=1,
                  env={"PATH": os.environ["PATH"]})
    assert r.timed_out and r.exit_code == -1
    assert time.monotonic() - started < 5, "background child kept the pipes open"


async def test_run_cancel_event_stops_command(tmp_path):
    cancel = asyncio.Event()
    asyncio.get_running_loop().call_later(0.5, cancel.set)
    r = await run(["sleep", "30"], cwd=tmp_path, timeout=20, env={"PATH": os.environ["PATH"]}, cancel=cancel)
    assert r.cancelled and not r.timed_out


async def test_run_caps_runaway_output_and_does_not_block(tmp_path):
    r = await run(["sh", "-c", "yes | head -c 3000000"], cwd=tmp_path, timeout=20,
                  env={"PATH": os.environ["PATH"]}, max_chars=1000)
    assert r.exit_code == 0 and not r.timed_out
    assert r.stdout.endswith("[output truncated]")
    assert len(r.stdout) < 1100


async def test_run_cancelled_task_kills_process_group(tmp_path):
    # The shell records its own pid, then sleeps. Cancelling the awaiting task must kill the group;
    # run() reaps the shell before re-raising, so os.kill(pid, 0) raising proves it is gone (not a zombie).
    pidfile = tmp_path / "pid"
    task = asyncio.ensure_future(run(["sh", "-c", f"echo $$ > {pidfile}; sleep 30"], cwd=tmp_path,
                                     timeout=20, env={"PATH": os.environ["PATH"]}))
    await asyncio.sleep(0.3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    pid = int(pidfile.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


async def test_subprocess_env_hides_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "secret")
    r = await run(["sh", "-c", 'echo "${GROQ_API_KEY:-absent}"'], cwd=tmp_path, timeout=10,
                  env=go_env(Settings()))
    assert r.stdout.strip() == "absent"
