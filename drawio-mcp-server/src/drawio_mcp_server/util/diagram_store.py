"""Filesystem-backed loader/saver for *.drawio files.

All paths are resolved relative to a sandbox root and rejected if they try to
escape it — Copilot is not allowed to read/write outside diagrams_dir.
"""

from __future__ import annotations

from pathlib import Path

from ..drawio.builder import build_drawio
from ..drawio.parser import parse_drawio
from ..types import Diagram
from .natural_sort import natural_key


class DiagramStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def list(self) -> list[str]:
        """Return diagram filenames in natural-ascending order.

        Uses the same natural-sort key as ``StoryStore`` so versioned names
        order intuitively: ``payments-v2.drawio`` < ``payments-v10.drawio``
        rather than the lexicographic ``payments-v10`` < ``payments-v2``.
        """
        self._ensure_root()
        return sorted(
            (p.name for p in self.root.iterdir() if p.is_file() and p.suffix == ".drawio"),
            key=natural_key,
        )

    def load(self, name: str) -> Diagram:
        full = self._safe_path(name)
        return parse_drawio(full.read_text(encoding="utf-8"))

    def save(self, name: str, diagram: Diagram) -> str:
        self._ensure_root()
        full = self._safe_path(name)
        full.write_text(build_drawio(diagram), encoding="utf-8")
        return str(full)

    def exists(self, name: str) -> bool:
        try:
            return self._safe_path(name).exists()
        except ValueError:
            return False

    def _ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, name: str) -> Path:
        filename = name if name.endswith(".drawio") else f"{name}.drawio"
        full = (self.root / filename).resolve()
        try:
            full.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"Refusing path outside diagrams root: {name}") from exc
        return full
