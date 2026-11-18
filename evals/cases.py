from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

QUESTIONS_FILE = Path(__file__).resolve().parent / "questions.yaml"
ANY_TOOL = "*"


@dataclass(frozen=True)
class EvalCase:
    id: str
    question: str
    expected_tools: list[str] = field(default_factory=list)
    # at least one of these must be called: for questions with several valid tool paths
    expected_any_tool: list[str] = field(default_factory=list)
    expected_args: dict[str, dict[str, Any]] = field(default_factory=dict)
    forbidden_tools: list[str] = field(default_factory=list)
    must_contain_any: list[str] = field(default_factory=list)
    must_not_contain: list[str] = field(default_factory=list)
    max_tool_calls: int | None = None
    max_calls_per_tool: dict[str, int] = field(default_factory=dict)
    judge: str | None = None


def parse_cases(raw: Any) -> list[EvalCase]:
    if not isinstance(raw, list):
        raise ValueError("questions file must contain a list of cases")
    cases = [EvalCase(**entry) for entry in raw]
    ids = [case.id for case in cases]
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicates:
        raise ValueError(f"duplicate case ids: {duplicates}")
    return cases


def load_cases(path: Path = QUESTIONS_FILE) -> list[EvalCase]:
    return parse_cases(yaml.safe_load(path.read_text(encoding="utf-8")))
