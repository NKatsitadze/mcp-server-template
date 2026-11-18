from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class AgentRun:
    answer: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    total_tokens: int = 0
    approval_requests: list[str] = field(default_factory=list)


def summarize_run(messages: list[BaseMessage], approval_requests: list[str] | None = None) -> AgentRun:
    """Reduce an agent's message history to what evals and the CLI need."""
    ai_messages = [message for message in messages if isinstance(message, AIMessage)]
    tool_calls = [
        ToolCall(name=call["name"], args=dict(call.get("args") or {}))
        for message in ai_messages
        for call in message.tool_calls
    ]
    total_tokens = sum((message.usage_metadata or {}).get("total_tokens", 0) for message in ai_messages)
    answer = ai_messages[-1].text if ai_messages else ""
    return AgentRun(
        answer=answer,
        tool_calls=tool_calls,
        total_tokens=total_tokens,
        approval_requests=list(approval_requests or []),
    )
