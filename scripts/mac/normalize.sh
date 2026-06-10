#!/usr/bin/env bash
# Cross-OS-friendly wrapper around scripts/normalize_jira_story.py.
# Locates the project venv created by scripts/mac/setup.sh and exec's
# the normalizer with all forwarded arguments.
#
# Usage:
#   ./scripts/mac/normalize.sh jira-stories/PROJ-124.txt
#   ./scripts/mac/normalize.sh jira-stories/PROJ-124.txt --diagram PROJ-123-20260524-045255.drawio
#   ./scripts/mac/normalize.sh jira-stories/PROJ-124.txt --check
#
# Why use this instead of `python scripts/normalize_jira_story.py ...`?
#   - It uses the venv's Python automatically (no need to source
#     activate first).
#   - It surfaces a clear error if setup.sh hasn't been run yet.
#   - The same command shape works on Linux (scripts/linux/normalize.sh)
#     and Windows (scripts/windows/normalize.ps1).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_PY="$REPO_ROOT/drawio-mcp-server/.venv/bin/python"
NORMALIZER="$REPO_ROOT/scripts/normalize_jira_story.py"

if [[ ! -x "$VENV_PY" ]]; then
  echo "venv Python missing at $VENV_PY — run scripts/mac/setup.sh first" >&2
  exit 1
fi
if [[ ! -f "$NORMALIZER" ]]; then
  echo "normalizer script missing at $NORMALIZER" >&2
  exit 1
fi

exec "$VENV_PY" "$NORMALIZER" "$@"
