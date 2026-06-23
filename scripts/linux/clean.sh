#!/usr/bin/env bash
# Remove the venv (and optionally generated artifacts) to reset the
# project to a fresh state.
#
# Usage:
#   bash scripts/linux/clean.sh              # venv only
#   bash scripts/linux/clean.sh --all        # venv + jira-stories + generated diagrams

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_DIR="$REPO_ROOT/drawio-mcp-server/.venv"

ALL=false
[[ "${1:-}" == "--all" ]] && ALL=true

if [[ -d "$VENV_DIR" ]]; then
  echo "Removing $VENV_DIR"
  rm -rf "$VENV_DIR"
else
  echo "venv already absent"
fi

# Pycache / build artifacts
find "$REPO_ROOT/drawio-mcp-server" \
  \( -name __pycache__ -o -name "*.egg-info" -o -name ".pytest_cache" \) \
  -prune -exec rm -rf {} + 2>/dev/null || true

if $ALL; then
  echo "--all: also removing jira-stories/DEMO-001.* and diagrams/*.drawio"
  # Note: jira-stories/PROJ-123.txt is the canonical worked-example
  # story (the normalizer's reference template lives at
  # template/surgical-story-template.txt) — leave PROJ-123.txt in place
  # so the docs and create/update prompts that point at it stay valid.
  rm -f "$REPO_ROOT/jira-stories/DEMO-001.txt"
  rm -f "$REPO_ROOT/jira-stories/DEMO-001-surgical.txt"
  rm -f "$REPO_ROOT/jira-stories/DEMO-001-connectors.md"
  find "$REPO_ROOT/diagrams" -maxdepth 1 -name "*.drawio" -type f -delete 2>/dev/null || true
  find "$REPO_ROOT/diagrams" -maxdepth 1 -name "*.drawio.bak" -type f -delete 2>/dev/null || true
fi

echo "Clean complete."
