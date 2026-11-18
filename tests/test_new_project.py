import subprocess
import sys
from pathlib import Path

import pytest

from scripts.new_project import COMMAND_TOKEN, PACKAGE_TOKEN, REPO_TOKEN, create_project, validate_name

TOKENS = (PACKAGE_TOKEN, COMMAND_TOKEN, REPO_TOKEN)


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return create_project("weather-mcp", tmp_path_factory.mktemp("out") / "weather-mcp", lock=False)


def test_package_command_and_server_are_renamed(project: Path) -> None:
    assert (project / "src" / "weather_mcp" / "server.py").is_file()
    assert not (project / "src" / PACKAGE_TOKEN).exists()
    pyproject = (project / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "weather-mcp"' in pyproject
    assert 'weather-mcp = "weather_mcp.server:main"' in pyproject
    assert 'SERVER_NAME = "weather-mcp"' in (project / "src/weather_mcp/server.py").read_text(
        encoding="utf-8"
    )


def test_copy_passes_lint_after_renaming(project: Path) -> None:
    """A new package name sorts differently, so the script must re-sort imports."""
    for command in (["check", str(project)], ["format", "--check", str(project)]):
        result = subprocess.run([sys.executable, "-m", "ruff", *command], capture_output=True, text=True)
        assert result.returncode == 0, result.stdout


def test_no_template_tokens_are_left(project: Path) -> None:
    for path in project.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for token in TOKENS:
                assert token not in text, f"{token} left in {path.relative_to(project)}"
                assert token not in path.name


def test_local_state_and_the_script_itself_are_not_copied(project: Path) -> None:
    for skipped in (".git", ".venv", "data", ".env", "evals/results", "scripts/new_project.py"):
        assert not (project / skipped).exists(), skipped
    assert not (project / "tests" / "test_new_project.py").exists()
    assert (project / "knowledge" / "overview.md").is_file()
    assert (project / "uv.lock").is_file()


@pytest.mark.parametrize("name", ["Weather", "1mcp", "my_mcp", "a--b", "-a", "class", "json", "mcp", "httpx"])
def test_bad_names_are_refused(name: str) -> None:
    with pytest.raises(ValueError):
        validate_name(name)


def test_existing_destination_is_refused(tmp_path: Path) -> None:
    with pytest.raises(FileExistsError):
        create_project("weather-mcp", tmp_path, lock=False)
