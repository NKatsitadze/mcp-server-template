from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from langgraph.types import Command

MAX_APPROVAL_ROUNDS = 5

ActionRequest = dict[str, Any]
Decision = dict[str, Any]
Decider = Callable[[list[ActionRequest]], list[Decision]]


@dataclass
class ApprovedRun:
    messages: list[Any]
    approval_requests: list[str] = field(default_factory=list)


def reject_all(requests: list[ActionRequest]) -> list[Decision]:
    """Decider for automated runs (evals): writes are proposed and checked, never executed."""
    message = "Rejected by the reviewer. The action was not executed; do not retry it."
    return [{"type": "reject", "message": message} for _ in requests]


async def run_with_approvals(
    agent: Any, question: str, decide: Decider, config: dict[str, Any]
) -> ApprovedRun:
    """Invoke the agent and answer every human-in-the-loop interrupt with `decide`.

    Each run gets its own thread_id, so paused state never leaks between questions.
    """
    run_config = {**config, "configurable": {**config.get("configurable", {}), "thread_id": str(uuid4())}}
    result = await agent.ainvoke({"messages": [{"role": "user", "content": question}]}, config=run_config)
    requested: list[str] = []
    for _ in range(MAX_APPROVAL_ROUNDS):
        interrupts = result.get("__interrupt__") or []
        if not interrupts:
            break
        requests = [request for interrupt in interrupts for request in interrupt.value["action_requests"]]
        requested.extend(request["name"] for request in requests)
        result = await agent.ainvoke(Command(resume={"decisions": decide(requests)}), config=run_config)
    else:
        raise RuntimeError(f"agent asked for approval more than {MAX_APPROVAL_ROUNDS} times")
    return ApprovedRun(messages=result["messages"], approval_requests=requested)
