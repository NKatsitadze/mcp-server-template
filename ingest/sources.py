"""What the docs index is built from. Add a LocalSource per folder you want searchable.

To index another repository, clone it first (a sparse, partial clone of only the folders you need;
see docs/PATTERNS.md) and point a LocalSource at the checkout.
"""

from dataclasses import dataclass
from pathlib import Path

from example_mcp.settings import PROJECT_ROOT


@dataclass(frozen=True)
class LocalSource:
    name: str
    root: Path
    globs: tuple[str, ...]

    def files(self) -> list[Path]:
        """Matching files in a stable order (stable chunk ids), each listed once."""
        found = {path for pattern in self.globs for path in self.root.glob(pattern) if path.is_file()}
        return sorted(found)


SOURCES: tuple[LocalSource, ...] = (
    LocalSource(name="knowledge", root=PROJECT_ROOT / "knowledge", globs=("**/*.md",)),
)
