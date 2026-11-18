from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.checkpoint.memory import InMemorySaver

from agent.prompt import SYSTEM_PROMPT
from agent.settings import AgentSettings
from example_mcp.settings import PROJECT_ROOT
from example_mcp.tools.writes import WRITE_TOOL_NAMES

SERVER_NAME = "example-mcp"
MAX_MODEL_CALLS_PER_RUN = 10
MAX_TOOL_CALLS_PER_RUN = 15


@dataclass(frozen=True)
class OpenAgent:
    graph: Any
    tool_names: frozenset[str]


def server_connection(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Launch the MCP server exactly like Claude Code does: a stdio child process run by uv.

    env is merged over the MCP SDK's minimal default environment (PATH, HOME, ...), and real env vars
    win over the server's .env, so evals can switch on the write tools without touching .env.
    """
    connection: dict[str, Any] = {
        "command": "uv",
        "args": ["--directory", str(PROJECT_ROOT), "run", "example-mcp"],
        "transport": "stdio",
    }
    if env:
        connection["env"] = env
    return connection


def approval_gates(tool_names: set[str]) -> dict[str, Any]:
    """Every write tool the server exposes pauses for a human decision; approve or reject only."""
    return {
        name: {"allowed_decisions": ["approve", "reject"], "description": f"{name} changes live data"}
        for name in WRITE_TOOL_NAMES
        if name in tool_names
    }


def build_model(model: str) -> BaseChatModel:
    """No temperature: reasoning models (GPT-5.x and others) reject a custom value."""
    return init_chat_model(model)


@asynccontextmanager
async def open_agent(
    settings: AgentSettings, server_env: dict[str, str] | None = None
) -> AsyncIterator[OpenAgent]:
    """Yield an agent bound to ONE persistent MCP session, plus the tool names it sees.

    client.get_tools() would start a new server process for every tool call; an explicit session keeps
    one process (and one backend login, for APIs that need one) for the whole run.
    Write tools are gated by HumanInTheLoopMiddleware; the checkpointer lets a paused run resume, so
    every invoke needs a config with a thread_id (run_with_approvals sets one).
    """
    client = MultiServerMCPClient({SERVER_NAME: server_connection(server_env)})
    async with client.session(SERVER_NAME) as session:
        tools = await load_mcp_tools(session, handle_tool_errors=True)
        agent = create_agent(
            model=build_model(settings.model),
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
            middleware=[
                HumanInTheLoopMiddleware(interrupt_on=approval_gates({tool.name for tool in tools})),
                ModelCallLimitMiddleware(run_limit=MAX_MODEL_CALLS_PER_RUN, exit_behavior="end"),
                ToolCallLimitMiddleware(run_limit=MAX_TOOL_CALLS_PER_RUN),
            ],
            checkpointer=InMemorySaver(),
        )
        yield OpenAgent(graph=agent, tool_names=frozenset(tool.name for tool in tools))
