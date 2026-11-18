from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from example_mcp.settings import ENV_FILE, load_env_file, require_provider_model


class AgentSettings(BaseSettings):
    """The test agent and evals. Models are provider:model strings for init_chat_model, e.g.
    openai:gpt-5.4-mini-2026-03-17 or anthropic:claude-sonnet-5-5. Pin dated snapshots where the
    provider offers them, so eval scores stay comparable over time. Provider keys (OPENAI_API_KEY,
    ANTHROPIC_API_KEY, ...) are read by the providers from the environment."""

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    model: str
    # Grades free-text eval answers with a yes/no verdict. Calibrate before trusting it
    # (uv run python -m evals.calibrate_judge): a weaker model can pass most labels and still confuse
    # look-alike values.
    judge_model: str = "openai:gpt-5.4-mini-2026-03-17"

    @field_validator("model", "judge_model")
    @classmethod
    def _provider_model(cls, value: str) -> str:
        return require_provider_model(value)


def load_agent_settings() -> AgentSettings:
    """Export .env first: providers and LangSmith read their settings from the process environment,
    and they must be set before any LangChain client is created."""
    load_env_file()
    return AgentSettings()
