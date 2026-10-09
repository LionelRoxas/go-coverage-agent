# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""One real Groq Writer call against a repo, to measure tokens and latency. Run inside the backend image."""
import asyncio
import sys
import time

from app.agents.context import ContextProvider
from app.agents.llm_agents import Agents
from app.agents.planner import plan
from app.config import Settings
from app.gotools import GoTools, read_module_info
from app.llm.client import GroqLLM
from app.llm.limits import RateLimiter, UsageLedger
from app.validator import Validator
from app.workspace import Workspace, resolve_repo, test_path_for


async def main(repo: str) -> None:
    s = Settings()
    ws = Workspace.create(s.work_dir, f"smoke-{int(time.time())}", resolve_repo(s.repos_dir, repo))
    ws.delete_existing_tests()
    tools = GoTools(ws.root, s)
    pkgs = await tools.list_packages(["examples/**", "testdata/**"])
    ws.seed_packages([(p.rel_dir, p.name) for p in pkgs])
    module, go_version = read_module_info(ws.root)
    funcs = await tools.funcs()
    validator = Validator(ws, tools, pkgs, funcs, module)
    baseline = (await validator.measure()).report
    print(f"baseline: {baseline.percent}% of {baseline.total_statements} statements")
    item = plan(baseline, {}, set(), max_items=1)[0]
    contexts = ContextProvider(ws, tools, funcs, await tools.symbols(), module, go_version, {p.rel_dir: p for p in pkgs})
    inputs = await contexts.inputs_for(item, baseline)

    async def emit(t, d):
        print("event:", t, d)

    llm = GroqLLM(s, UsageLedger(s.output_dir / ".usage.json", s.daily_token_budget), RateLimiter(), emit=emit)
    started = time.monotonic()
    snippet, usage = await Agents(llm, s.max_prompt_tokens).write(item, inputs)
    print(f"target: {item.file} {[k.label() for k in item.functions]}")
    print(f"usage: prompt={usage.prompt_tokens} completion={usage.completion_tokens} seconds={time.monotonic() - started:.1f}")
    print(snippet.code)
    result = await validator.validate(test_path_for(item.file), inputs.package, snippet, baseline)
    print("validation:", result.kind.value, result.report.percent if result.report else None)
    print(result.output[:2000])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "stats"))
