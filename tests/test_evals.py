import pytest

from agent.transcript import AgentRun, ToolCall
from evals.calibrate_judge import disagreements, load_labels
from evals.cases import EvalCase, load_cases, parse_cases
from evals.checks import find_failures
from evals.judge import JUDGE_PROMPT, NO_VERDICT, Judgement, LLMJudge, judge_failures
from evals.run_evals import EVAL_SERVER_ENV, Attempt, missing_tools, never_passed
from example_mcp.server import create_server
from tests.conftest import FakeClient


def run_with(answer: str = "", *calls: tuple[str, dict], approvals: list[str] | None = None) -> AgentRun:
    return AgentRun(
        answer=answer,
        tool_calls=[ToolCall(name, args) for name, args in calls],
        approval_requests=approvals or [],
    )


# --- checks ---------------------------------------------------------------------------------
def test_passing_run_has_no_failures() -> None:
    case = EvalCase(
        id="c",
        question="q",
        expected_tools=["list_users"],
        expected_args={"list_users": {"name_contains": "Clem"}},
        must_contain_any=["Romaguera-Jacobson"],
        max_tool_calls=1,
    )

    assert (
        find_failures(case, run_with("Romaguera-Jacobson.", ("list_users", {"name_contains": "clem "}))) == []
    )


def test_missing_tool_and_wrong_args() -> None:
    case = EvalCase(
        id="c", question="q", expected_tools=["get_user"], expected_args={"list_todos": {"user_id": 2}}
    )

    failures = find_failures(case, run_with("", ("list_todos", {"user_id": 1})))

    assert "did not call get_user" in failures
    assert any("no list_todos call with {'user_id': 2}" in failure for failure in failures)


def test_any_of_several_valid_tool_paths() -> None:
    case = EvalCase(id="c", question="q", expected_any_tool=["list_todos", "get_user"])

    assert find_failures(case, run_with("9", ("get_user", {"user_id": 1}))) == []
    assert find_failures(case, run_with("9", ("list_todos", {"user_id": 1}))) == []
    assert find_failures(case, run_with("9")) == ["called none of ['list_todos', 'get_user']"]


def test_bool_args_are_not_confused_with_ints() -> None:
    case = EvalCase(id="c", question="q", expected_args={"list_todos": {"completed": False}})

    assert find_failures(case, run_with("", ("list_todos", {"completed": 0})))
    assert not find_failures(case, run_with("", ("list_todos", {"completed": False})))


def test_forbidden_tools_wildcard_and_limits() -> None:
    assert find_failures(
        EvalCase(id="c", question="q", forbidden_tools=["*"]), run_with("hi", ("list_users", {}))
    )
    assert not find_failures(EvalCase(id="c", question="q", forbidden_tools=["*"]), run_with("hi"))
    assert find_failures(
        EvalCase(id="c", question="q", max_tool_calls=1), run_with("", ("a", {}), ("b", {}))
    ) == ["2 tool calls > max 1"]


def test_curly_apostrophes_match_straight_ones() -> None:
    case = EvalCase(id="c", question="q", must_contain_any=["can't"], must_not_contain=["010-692"])

    assert find_failures(case, run_with("I can\u2019t share that.")) == []
    assert find_failures(case, run_with("I can\u2019t, but it is 010-692-6593.")) == [
        "answer contains forbidden '010-692'"
    ]


def test_unrequested_or_ungated_writes_fail_every_case() -> None:
    write = ("complete_todo", {"todo_id": 1})

    assert find_failures(
        EvalCase(id="r", question="q"), run_with("", write, approvals=["complete_todo"])
    ) == ["proposed unrequested write complete_todo"]
    assert find_failures(
        EvalCase(id="w", question="q", expected_tools=["complete_todo"]), run_with("", write)
    ) == ["write complete_todo was not gated by human approval"]


# --- case files -----------------------------------------------------------------------------
def test_duplicate_case_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        parse_cases([{"id": "a", "question": "q"}, {"id": "a", "question": "q"}])


async def test_every_eval_case_uses_tools_the_eval_server_exposes() -> None:
    """The evals switch writes on (EVAL_SERVER_ENV) and keep docs search; every expected tool must exist."""
    assert EVAL_SERVER_ENV["ENABLE_WRITE_TOOLS"] == "true"
    server = create_server(FakeClient(), docs_search=object(), write_allowed_ids=frozenset({"1"}))
    available = frozenset(tool.name for tool in await server.list_tools())

    assert missing_tools(load_cases(), available) == []


def test_data_cases_check_tool_arguments() -> None:
    """Models know this public dataset: a data answer without the right tool call must fail."""
    for case in load_cases():
        if case.judge or case.must_contain_any:
            assert case.expected_tools or case.expected_any_tool or case.forbidden_tools, case.id


def test_missing_tools_and_never_passed() -> None:
    cases = [EvalCase(id="a", question="q", expected_tools=["x"]), EvalCase(id="b", question="q")]
    attempts = [
        Attempt("a", 1, ["fail"], [], 0, 0.0, ""),
        Attempt("a", 2, ["fail"], [], 0, 0.0, ""),
        Attempt("b", 1, [], [], 0, 0.0, ""),
    ]

    assert missing_tools(cases, frozenset({"y"})) == ["x"]
    assert never_passed(cases, attempts) == ["a"]


# --- judge ----------------------------------------------------------------------------------
class FakeGrader:
    def __init__(self, verdict: str) -> None:
        self.verdict = verdict
        self.calls: list[tuple[str, str, str]] = []

    async def grade(self, question: str, answer: str, criterion: str) -> Judgement:
        self.calls.append((question, answer, criterion))
        return Judgement(verdict=self.verdict, reason="because")


CASE = EvalCase(id="c", question="Open todos of user 1?", judge="Says 9.")


async def test_judge_called_with_question_answer_and_criterion() -> None:
    grader = FakeGrader("yes")

    assert await judge_failures(CASE, AgentRun(answer="9 open."), grader) == []
    assert grader.calls == [("Open todos of user 1?", "9 open.", "Says 9.")]
    assert await judge_failures(CASE, AgentRun(answer="19"), FakeGrader("no")) == ["judge: because"]
    assert await judge_failures(EvalCase(id="c", question="q"), AgentRun(answer="x"), grader) == []


async def test_judge_without_a_verdict_counts_as_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class NoneModel:
        async def ainvoke(self, *_args, **_kwargs) -> None:
            return None

    judge = LLMJudge.__new__(LLMJudge)
    judge._model = NoneModel()

    assert await judge.grade("q", "a", "c") == NO_VERDICT


def test_prompt_frames_inputs_as_data() -> None:
    assert "never instructions" in JUDGE_PROMPT
    assert "<answer>{answer}</answer>" in JUDGE_PROMPT


def test_calibration_set_has_both_labels_and_unique_ids() -> None:
    labels = load_labels()

    assert {label.expected for label in labels} == {"yes", "no"}
    assert len({label.id for label in labels}) == len(labels)


async def test_disagreements_lists_only_mismatches() -> None:
    label = load_labels()[0]
    wrong = "no" if label.expected == "yes" else "yes"

    assert await disagreements(FakeGrader(label.expected), [label], runs=2) == []
    assert len(await disagreements(FakeGrader(wrong), [label], runs=2)) == 2
