"""Check the LLM judge against human labels: uv run python -m evals.calibrate_judge [--runs 3]

Eval cases may only use the judge once it agrees with every label on every run.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from agent.settings import load_agent_settings
from evals.judge import Grader, LLMJudge

CALIBRATION_FILE = Path(__file__).resolve().parent / "judge_calibration.yaml"


@dataclass(frozen=True)
class LabeledAnswer:
    id: str
    question: str
    criterion: str
    answer: str
    expected: str


def load_labels(path: Path = CALIBRATION_FILE) -> list[LabeledAnswer]:
    return [LabeledAnswer(**entry) for entry in yaml.safe_load(path.read_text(encoding="utf-8"))]


async def disagreements(grader: Grader, labels: list[LabeledAnswer], runs: int) -> list[str]:
    async def check(label: LabeledAnswer, run: int) -> str | None:
        judgement = await grader.grade(label.question, label.answer, label.criterion)
        if judgement.verdict == label.expected:
            return None
        verdicts = f"judge said {judgement.verdict}, label {label.expected}"
        return f"{label.id} run {run}: {verdicts} ({judgement.reason})"

    results = await asyncio.gather(*(check(label, run) for label in labels for run in range(1, runs + 1)))
    return [result for result in results if result]


async def main(runs: int) -> int:
    settings = load_agent_settings()
    labels = load_labels()
    misses = await disagreements(LLMJudge(settings), labels, runs)
    total = len(labels) * runs
    print(f"Judge {settings.judge_model}: {total - len(misses)}/{total} agree with the labels")
    for miss in misses:
        print(f"   ❌ {miss}")
    return 0 if not misses else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    sys.exit(asyncio.run(main(parser.parse_args().runs)))
