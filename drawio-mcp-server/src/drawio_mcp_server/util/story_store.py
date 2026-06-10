"""Read-only loader for downloaded Jira story summaries.

Accepts plain text, markdown, or json files placed under the configured
stories directory. The server never writes here.
"""

from __future__ import annotations

from pathlib import Path

from .natural_sort import natural_key

ALLOWED_SUFFIXES = {".txt", ".md", ".json"}


class StoryStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def list(self) -> list[str]:
        """Return story filenames in natural-ascending (low-to-high) order.

        Natural sort is used so that Jira-style keys order intuitively:
        ``PROJ-2`` < ``PROJ-10`` < ``PROJ-100`` rather than the lexicographic
        ``PROJ-10`` < ``PROJ-100`` < ``PROJ-2``.
        """
        if not self.root.exists():
            return []
        return sorted(
            (
                p.name
                for p in self.root.iterdir()
                if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES
            ),
            key=natural_key,
        )

    def read(self, name: str) -> str:
        full = (self.root / name).resolve()
        try:
            full.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"Refusing path outside stories root: {name}") from exc
        return full.read_text(encoding="utf-8")
