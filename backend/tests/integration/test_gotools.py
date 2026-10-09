# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import asyncio
import os
import time

import pytest

from app.coverage import parse_profile, summarize
from app.gotools import read_module_info, run

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
