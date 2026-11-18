"""Run the eval set: uv run python -m evals.run_evals [--runs 3] [--case ID ...] [--concurrency 4]

Exits 1 when the pass rate is below the threshold OR any case failed every run (one broken
behaviour must not hide inside a good average).
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agent.approvals import reject_all, run_with_approvals
from agent.factory import open_agent
from agent.prompt import SYSTEM_PROMPT_VERSION
from agent.settings import AgentSettings, load_agent_settings
from agent.transcript import AgentRun, summarize_run
from evals.cases import EvalCase, load_cases
from evals.checks import find_failures
from evals.judge import Grader, LLMJudge, judge_failures

RESULTS_DIR = Path(__file__).resolve().parent / "results"
PASS_THRESHOLD = 0.9
RECURSION_LIMIT = 25
# Evals exercise the write tools too: proposals are always rejected (reject_all), so nothing is
# changed. Passed as real env vars, which win over the server's .env.
EVAL_SERVER_ENV = {"ENABLE_WRITE_TOOLS": "true", "WRITE_ALLOWED_IDS": "1"}


@dataclass(frozen=True)
class Attempt:
    case_id: str
    attempt: int
    failures: list[str]
    tool_calls: list[str]
    total_tokens: int
    seconds: float
    answer: str


def missing_tools(cases: list[EvalCase], available: frozenset[str]) -> list[str]:
    """Tools the cases expect that the server does not expose (e.g. writes switched off)."""
    expected = {
        tool
        for case in cases
        for tool in [*case.expected_tools, *case.expected_any_tool, *case.expected_args]
    }
    return sorted(expected - available)


def never_passed(cases: list[EvalCase], attempts: list[Attempt]) -> list[str]:
    return [
        case.id
        for case in cases
        if not any(not attempt.failures for attempt in attempts if attempt.case_id == case.id)
    ]


async def run_attempt(agent: Any, case: EvalCase, attempt: int, model: str, grader: Grader) -> Attempt:
    started = time.monotonic()
    try:
        approved = await run_with_approvals(
            agent,
            case.question,
            reject_all,
            config={
                "recursion_limit": RECURSION_LIMIT,
                "run_name": f"eval:{case.id}",
                "tags": ["eval", case.id],
                "metadata": {"prompt_version": SYSTEM_PROMPT_VERSION, "model": model, "attempt": attempt},
            },
        )
        run = summarize_run(approved.messages, approved.approval_requests)
        failures = find_failures(case, run) + await judge_failures(case, run, grader)
    except Exception as error:  # one crashed attempt must not abort the whole eval run
        run = AgentRun(answer="")
        failures = [f"crashed: {type(error).__name__}: {error}"]
    return Attempt(
        case_id=case.id,
        attempt=attempt,
        failures=failures,
        tool_calls=[f"{call.name}({call.args})" for call in run.tool_calls],
        total_tokens=run.total_tokens,
        seconds=round(time.monotonic() - started, 1),
        answer=run.answer,
    )


def print_report(cases: list[EvalCase], attempts: list[Attempt]) -> float:
    print(f"\n{'case':<30} pass  notes")
    for case in cases:
        own = [attempt for attempt in attempts if attempt.case_id == case.id]
        passed = sum(not attempt.failures for attempt in own)
        mark = "✅" if passed == len(own) else ("⚠️" if passed else "❌")
        print(f"{mark} {case.id:<28} {passed}/{len(own)}")
        for attempt in own:
            for failure in attempt.failures:
                print(f"      #{attempt.attempt}: {failure}")
    total_passed = sum(not attempt.failures for attempt in attempts)
    rate = total_passed / len(attempts) if attempts else 0.0
    tokens = sum(attempt.total_tokens for attempt in attempts)
    print(
        f"\nOverall: {total_passed}/{len(attempts)} = {rate:.0%}"
        f" (threshold {PASS_THRESHOLD:.0%}) | {tokens} tokens"
    )
    return rate


def save_report(attempts: list[Attempt], settings: AgentSettings, rate: float) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    report = {
        "model": settings.model,
        "judge_model": settings.judge_model,
        "prompt_version": SYSTEM_PROMPT_VERSION,
        "pass_rate": rate,
        "attempts": [asdict(attempt) for attempt in attempts],
    }
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


async def main(runs: int, case_ids: list[str], concurrency: int) -> bool:
    settings = load_agent_settings()
    cases = [case for case in load_cases() if not case_ids or case.id in case_ids]
    if not cases:
        sys.exit(f"No cases match {case_ids}")
    print(
        f"Running {len(cases)} case(s) x {runs} with {settings.model}, prompt {SYSTEM_PROMPT_VERSION},"
        f" judge {settings.judge_model}"
    )
    grader = LLMJudge(settings)

    limiter = asyncio.Semaphore(concurrency)
    async with open_agent(settings, server_env=EVAL_SERVER_ENV) as agent:
        missing = missing_tools(cases, agent.tool_names)
        if missing:
            sys.exit(f"The server does not expose {missing}; check .env (DOCS_SEARCH, write tools).")

        async def limited(case: EvalCase, attempt: int) -> Attempt:
            async with limiter:
                return await run_attempt(agent.graph, case, attempt, settings.model, grader)

        attempts = list(
            await asyncio.gather(
                *(limited(case, attempt) for case in cases for attempt in range(1, runs + 1))
            )
        )

    rate = print_report(cases, attempts)
    print(f"Report: {save_report(attempts, settings, rate)}")
    failed_everywhere = never_passed(cases, attempts)
    if failed_everywhere:
        print(f"❌ failed every run: {', '.join(failed_everywhere)}")
    return rate >= PASS_THRESHOLD and not failed_everywhere


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--case", action="append", default=[], dest="case_ids")
    parser.add_argument("--concurrency", type=int, default=4)
    options = parser.parse_args()
    sys.exit(0 if asyncio.run(main(options.runs, options.case_ids, options.concurrency)) else 1)
