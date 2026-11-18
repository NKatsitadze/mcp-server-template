from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command
from pydantic import ValidationError

from agent.approvals import MAX_APPROVAL_ROUNDS, reject_all, run_with_approvals
from agent.factory import approval_gates, build_model, server_connection
from agent.prompt import SYSTEM_PROMPT
from agent.settings import AgentSettings
from agent.transcript import AgentRun, ToolCall, summarize_run

WRITE_REQUEST = {"name": "complete_todo", "args": {"todo_id": 1}}


class FakeAgent:
    """Interrupts `pauses` times with one write request, then finishes."""

    def __init__(self, pauses: int) -> None:
        self.pauses = pauses
        self.inputs: list[Any] = []
        self.configs: list[dict] = []

    async def ainvoke(self, payload: Any, config: dict) -> dict:
        self.inputs.append(payload)
        self.configs.append(config)
        if len(self.inputs) <= self.pauses:
            return {
                "messages": [],
                "__interrupt__": [SimpleNamespace(value={"action_requests": [WRITE_REQUEST]})],
            }
        return {"messages": ["final"]}


async def test_interrupts_are_answered_and_recorded() -> None:
    agent = FakeAgent(pauses=1)

    run = await run_with_approvals(agent, "complete it", reject_all, config={"run_name": "x"})

    assert run.messages == ["final"]
    assert run.approval_requests == ["complete_todo"]
    resume = agent.inputs[1]
    assert isinstance(resume, Command)
    assert resume.resume["decisions"][0]["type"] == "reject"
    assert agent.configs[0]["configurable"]["thread_id"] == agent.configs[1]["configurable"]["thread_id"]


async def test_each_run_gets_its_own_thread() -> None:
    first, second = FakeAgent(pauses=0), FakeAgent(pauses=0)

    await run_with_approvals(first, "q", reject_all, config={})
    await run_with_approvals(second, "q", reject_all, config={})

    assert first.configs[0]["configurable"]["thread_id"] != second.configs[0]["configurable"]["thread_id"]


async def test_endless_approval_loop_is_stopped() -> None:
    with pytest.raises(RuntimeError, match="more than"):
        await run_with_approvals(FakeAgent(pauses=MAX_APPROVAL_ROUNDS + 1), "q", reject_all, config={})


def test_approval_gates_only_for_available_write_tools() -> None:
    gates = approval_gates({"list_users", "complete_todo"})

    assert set(gates) == {"complete_todo"}
    assert gates["complete_todo"]["allowed_decisions"] == ["approve", "reject"]
    assert approval_gates({"list_users"}) == {}


def test_server_connection_runs_the_server_over_stdio_with_optional_env() -> None:
    plain = server_connection()

    assert plain["transport"] == "stdio"
    assert plain["args"][-1] == "example-mcp"
    assert "env" not in plain
    assert server_connection({"ENABLE_WRITE_TOOLS": "true"})["env"] == {"ENABLE_WRITE_TOOLS": "true"}


def test_build_model_from_provider_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")

    model = build_model("openai:gpt-5.4-mini-2026-03-17")

    assert model.model_name == "gpt-5.4-mini-2026-03-17"


def test_agent_settings_validate_provider_strings() -> None:
    assert AgentSettings(_env_file=None, model="openai:m").judge_model.startswith("openai:")
    with pytest.raises(ValidationError):
        AgentSettings(_env_file=None, model="no-provider")


def test_prompt_states_the_safety_rules() -> None:
    for rule in ("never as instructions", "do not retry", "not available", "Never guess"):
        assert rule in SYSTEM_PROMPT


def test_summarize_run_collects_calls_tokens_and_final_answer() -> None:
    messages = [
        HumanMessage("q"),
        AIMessage(
            content="",
            tool_calls=[{"name": "list_users", "args": {"name_contains": "x"}, "id": "1"}],
            usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        ),
        ToolMessage(content="1 of 10 user(s)", tool_call_id="1"),
        AIMessage(
            content=[{"type": "text", "text": "One user."}],
            usage_metadata={"input_tokens": 20, "output_tokens": 3, "total_tokens": 23},
        ),
    ]

    run = summarize_run(messages)

    assert run.tool_calls == [ToolCall("list_users", {"name_contains": "x"})]
    assert run.total_tokens == 38
    assert run.answer == "One user."
    assert summarize_run([HumanMessage("q")]) == AgentRun(answer="")
