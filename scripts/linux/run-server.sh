#!/usr/bin/env bash
# Run the MCP server in the foreground (stdio). Use for debugging
# without VS Code. The server will block waiting for JSON-RPC on stdin.
# Press Ctrl+C to stop.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_PY="$REPO_ROOT/drawio-mcp-server/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  echo "venv Python missing at $VENV_PY — run scripts/linux/setup.sh first" >&2
  exit 1
fi

export DRAWIO_DIAGRAMS_DIR="$REPO_ROOT/diagrams"
export DRAWIO_STORIES_DIR="$REPO_ROOT/jira-stories"
export PYTHONPATH="$REPO_ROOT/drawio-mcp-server/src"
export PYTHONFAULTHANDLER=1

echo "Launching drawio MCP server (Ctrl+C to stop)"
echo "  DRAWIO_DIAGRAMS_DIR = $DRAWIO_DIAGRAMS_DIR"
echo "  DRAWIO_STORIES_DIR  = $DRAWIO_STORIES_DIR"
echo
exec "$VENV_PY" -m drawio_mcp_server
