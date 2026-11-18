"""Ask the agent one question: uv run python -m agent.chat "how many open todos does user 1 have?"

Write actions pause and ask for your approval in the terminal before they run. Write tools exist
only when ENABLE_WRITE_TOOLS=true in .env.
"""

import asyncio
import sys

from agent.approvals import ActionRequest, Decision, run_with_approvals
from agent.factory import open_agent
from agent.prompt import SYSTEM_PROMPT_VERSION
from agent.settings import load_agent_settings
from agent.transcript import summarize_run


def ask_human(requests: list[ActionRequest]) -> list[Decision]:
    decisions: list[Decision] = []
    for request in requests:
        print(f"\n⚠️  The agent wants to run a WRITE action: {request['name']}({request['args']})")
        answer = input("   Approve? [y/N] ").strip().casefold()
        decisions.append({"type": "approve"} if answer in ("y", "yes") else {"type": "reject"})
    return decisions


async def ask(question: str) -> None:
    settings = load_agent_settings()
    async with open_agent(settings) as agent:
        approved = await run_with_approvals(
            agent.graph,
            question,
            ask_human,
            config={"run_name": "chat", "metadata": {"prompt_version": SYSTEM_PROMPT_VERSION}},
        )
    run = summarize_run(approved.messages, approved.approval_requests)
    for call in run.tool_calls:
        print(f"→ {call.name}({call.args})")
    print(f"\n{run.answer}\n\n[{run.total_tokens} tokens, model {settings.model}]")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit('Usage: uv run python -m agent.chat "<question>"')
    asyncio.run(ask(sys.argv[1]))
