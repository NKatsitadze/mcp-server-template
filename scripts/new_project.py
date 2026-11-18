"""Start a new MCP server from this template: uv run python scripts/new_project.py weather-mcp

Copies the template next to it (or into --dest), renames the package, the command and the server
name, and refreshes uv.lock. The copy is a normal project with its own tests and evals; this script and
its test are not copied.
"""

import argparse
import importlib.util
import keyword
import re
import shutil
import subprocess
import sys
from pathlib import Path

TEMPLATE_ROOT = Path(__file__).resolve().parents[1]
# Built from parts so that a copy of this file could never rewrite its own tokens.
PACKAGE_TOKEN = "example" + "_mcp"
COMMAND_TOKEN = "example" + "-mcp"
REPO_TOKEN = "mcp-server" + "-template"
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
SKIPPED_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".env",
}
SKIPPED_RELATIVE = {"data", "evals/results", "scripts/new_project.py", "tests/test_new_project.py"}


def package_name(name: str) -> str:
    return name.replace("-", "_")


def validate_name(name: str) -> None:
    """Refuse names that would break the copy: invalid identifiers, keywords, or a package that
    would shadow the standard library or an installed dependency (a project called `mcp` would
    import itself instead of the MCP SDK)."""
    if not NAME_PATTERN.match(name):
        raise ValueError("use lowercase letters, digits and single hyphens, starting with a letter")
    package = package_name(name)
    if keyword.iskeyword(package):
        raise ValueError(f"{package} is a Python keyword")
    if package in sys.stdlib_module_names or importlib.util.find_spec(package) is not None:
        raise ValueError(f"{package} would shadow an existing module")
    if package == PACKAGE_TOKEN:
        raise ValueError("pick a new name")


def is_skipped(relative: Path) -> bool:
    return bool(set(relative.parts) & SKIPPED_NAMES) or any(
        relative.as_posix() == skipped or relative.as_posix().startswith(f"{skipped}/")
        for skipped in SKIPPED_RELATIVE
    )


def copy_template(source: Path, destination: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        base = Path(directory).relative_to(source)
        return {name for name in names if is_skipped(base / name)}

    shutil.copytree(source, destination, ignore=ignore)


def replace_tokens(root: Path, name: str) -> None:
    """Rewrite the tokens in every UTF-8 text file, then rename paths, deepest first, so a parent is
    never renamed before its children."""
    replacements = ((PACKAGE_TOKEN, package_name(name)), (COMMAND_TOKEN, name), (REPO_TOKEN, name))
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # binary file
        updated = text
        for old, new in replacements:
            updated = updated.replace(old, new)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        new_name = path.name
        for old, new in replacements:
            new_name = new_name.replace(old, new)
        if new_name != path.name:
            path.rename(path.with_name(new_name))


def tidy_imports(root: Path) -> None:
    """The new package name sorts differently from the old one (demo_mcp before evals), so re-sort
    imports and re-format with the template's own ruff, using the copy's pyproject settings."""
    ruff = [sys.executable, "-m", "ruff"]
    quiet = {"check": True, "capture_output": True}
    subprocess.run([*ruff, "check", "--fix", "--select", "I", str(root)], **quiet)
    subprocess.run([*ruff, "format", str(root)], **quiet)


def create_project(name: str, destination: Path, lock: bool = True) -> Path:
    validate_name(name)
    if destination.exists():
        raise FileExistsError(f"{destination} already exists")
    copy_template(TEMPLATE_ROOT, destination)
    replace_tokens(destination, name)
    tidy_imports(destination)
    if lock:
        # Rewrites the renamed root package in uv.lock; every dependency keeps its locked version.
        subprocess.run(["uv", "lock", "--directory", str(destination)], check=True)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("name", help="project name, e.g. weather-mcp (package weather_mcp)")
    parser.add_argument("--dest", type=Path, help="target folder (default: next to the template)")
    parser.add_argument("--no-lock", action="store_true", help="skip `uv lock` (tests only)")
    options = parser.parse_args()
    destination = (options.dest or TEMPLATE_ROOT.parent / options.name).resolve()
    try:
        create_project(options.name, destination, lock=not options.no_lock)
    except (ValueError, FileExistsError) as error:
        sys.exit(f"❌ {error}")
    print(
        f"✅ Created {destination}\n\nNext steps:\n"
        f"  cd {destination}\n"
        "  git init -b main && uv sync\n"
        "  cp .env.example .env        # then fill in your API and model settings\n"
        "  uv run pytest\n"
        "  Replace the example tools (README: 'Add a tool in 5 steps')."
    )


if __name__ == "__main__":
    main()
