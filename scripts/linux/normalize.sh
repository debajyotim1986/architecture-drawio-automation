#!/usr/bin/env bash
# Cross-OS-friendly wrapper around scripts/normalize_jira_story.py.
# Locates the project venv created by scripts/linux/setup.sh and exec's
# the normalizer with all forwarded arguments.
#
# Usage:
#   ./scripts/linux/normalize.sh jira-stories/PROJ-124.txt
#   ./scripts/linux/normalize.sh jira-stories/PROJ-124.txt --diagram PROJ-123-20260524-045255.drawio
#   ./scripts/linux/normalize.sh jira-stories/PROJ-124.txt --check
#
# Identical behavior to scripts/mac/normalize.sh — the only difference
# is the error message points at the Linux setup script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_PY="$REPO_ROOT/drawio-mcp-server/.venv/bin/python"
NORMALIZER="$REPO_ROOT/scripts/normalize_jira_story.py"

if [[ ! -x "$VENV_PY" ]]; then
  echo "venv Python missing at $VENV_PY — run scripts/linux/setup.sh first" >&2
  exit 1
fi
if [[ ! -f "$NORMALIZER" ]]; then
  echo "normalizer script missing at $NORMALIZER" >&2
  exit 1
fi

exec "$VENV_PY" "$NORMALIZER" "$@"
