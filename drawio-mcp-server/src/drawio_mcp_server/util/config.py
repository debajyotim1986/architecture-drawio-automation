"""Server configuration, sourced from environment variables.

The same binary can be wired into different workspaces without code changes:
    DRAWIO_DIAGRAMS_DIR  defaults to <cwd>/diagrams
    DRAWIO_STORIES_DIR   defaults to <cwd>/jira-stories
    DRAWIO_ICONS_DIR     defaults to <cwd>/logo_icon_gcp
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ServerConfig:
    diagrams_dir: Path
    stories_dir: Path
    icons_dir: Path


def resolve_config() -> ServerConfig:
    cwd = Path.cwd()
    diagrams_dir = Path(
        os.environ.get("DRAWIO_DIAGRAMS_DIR", cwd / "diagrams")
    ).resolve()
    stories_dir = Path(
        os.environ.get("DRAWIO_STORIES_DIR", cwd / "jira-stories")
    ).resolve()
    icons_dir = Path(
        os.environ.get("DRAWIO_ICONS_DIR", cwd / "logo_icon_gcp")
    ).resolve()
    return ServerConfig(
        diagrams_dir=diagrams_dir,
        stories_dir=stories_dir,
        icons_dir=icons_dir,
    )
