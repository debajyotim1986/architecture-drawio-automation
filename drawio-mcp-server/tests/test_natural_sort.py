"""Tests for natural-sort behaviour of StoryStore and DiagramStore."""

from __future__ import annotations

from pathlib import Path

from drawio_mcp_server.util.diagram_store import DiagramStore
from drawio_mcp_server.util.natural_sort import natural_key
from drawio_mcp_server.util.story_store import StoryStore


def test_natural_key_orders_jira_keys_numerically() -> None:
    names = ["PROJ-10.txt", "PROJ-2.txt", "PROJ-1.txt", "PROJ-100.txt", "PROJ-21.txt"]
    assert sorted(names, key=natural_key) == [
        "PROJ-1.txt",
        "PROJ-2.txt",
        "PROJ-10.txt",
        "PROJ-21.txt",
        "PROJ-100.txt",
    ]


def test_natural_key_mixes_projects_case_insensitively() -> None:
    names = ["abc-3.md", "ABC-2.txt", "PROJ-1.txt", "abc-10.md"]
    # Case folding: abc and ABC compare equal, then numbers decide.
    assert sorted(names, key=natural_key) == [
        "ABC-2.txt",
        "abc-3.md",
        "abc-10.md",
        "PROJ-1.txt",
    ]


def test_story_store_lists_in_natural_order(tmp_path: Path) -> None:
    for name in ("PROJ-10.txt", "PROJ-2.txt", "PROJ-1.txt", "PROJ-100.md"):
        (tmp_path / name).write_text("x")
    assert StoryStore(tmp_path).list() == [
        "PROJ-1.txt",
        "PROJ-2.txt",
        "PROJ-10.txt",
        "PROJ-100.md",
    ]


def test_story_store_skips_unsupported_suffixes(tmp_path: Path) -> None:
    (tmp_path / "PROJ-1.txt").write_text("x")
    (tmp_path / "PROJ-2.exe").write_text("x")
    (tmp_path / "PROJ-3.md").write_text("x")
    assert StoryStore(tmp_path).list() == ["PROJ-1.txt", "PROJ-3.md"]


def test_diagram_store_lists_in_natural_order(tmp_path: Path) -> None:
    for name in ("payments-v10.drawio", "payments-v2.drawio", "payments-v1.drawio"):
        (tmp_path / name).write_text("<x/>")
    assert DiagramStore(tmp_path).list() == [
        "payments-v1.drawio",
        "payments-v2.drawio",
        "payments-v10.drawio",
    ]
