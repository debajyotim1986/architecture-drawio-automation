#!/usr/bin/env bash
# Probe the MCP server with a tools/list JSON-RPC call and confirm
# all 13 tools are present.

set -euo pipefail

if [[ -t 1 ]]; then
  C_BOLD=$'\033[1m'; C_RED=$'\033[31m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RESET=$'\033[0m'
else
  C_BOLD=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_RESET=""
fi
ok()   { printf "%s✓%s %s\n" "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf "%s!%s %s\n" "$C_YELLOW" "$C_RESET" "$*"; }
die()  { printf "%s✗%s %s\n" "$C_RED" "$C_RESET" "$*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_PY="$REPO_ROOT/drawio-mcp-server/.venv/bin/python"

[[ -x "$VENV_PY" ]] || die "venv Python missing at $VENV_PY — run scripts/linux/setup.sh first"

EXPECTED=(list_diagrams read_diagram read_diagram_summary create_diagram \
          add_container add_node add_edge add_title add_connector_table \
          update_node remove_element \
          list_stories read_story)

# Probe via tools/list
INIT='{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"verify.sh","version":"1.0"}}}'
INITED='{"jsonrpc":"2.0","method":"notifications/initialized"}'
LIST='{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

OUT="$(printf '%s\n%s\n%s\n' "$INIT" "$INITED" "$LIST" \
       | DRAWIO_DIAGRAMS_DIR="$REPO_ROOT/diagrams" \
         DRAWIO_STORIES_DIR="$REPO_ROOT/jira-stories" \
         PYTHONPATH="$REPO_ROOT/drawio-mcp-server/src" \
         "$VENV_PY" -m drawio_mcp_server 2>/dev/null || true)"

if [[ -z "$OUT" ]]; then
  die "Server produced no output. Run scripts/linux/run-server.sh to see errors."
fi

# Pull tool names from the response with python (jq not assumed installed).
# Pass $OUT via env var, NOT via heredoc interpolation — JSON content can
# contain \n / backslashes that Python would otherwise interpret as escapes.
NAMES="$(MCP_OUT="$OUT" "$VENV_PY" - <<'PYEOF'
import json, os
out = os.environ.get("MCP_OUT", "")
names = []
for line in out.splitlines():
    line = line.strip()
    if not line: continue
    try:
        msg = json.loads(line)
    except Exception:
        continue
    tools = (msg.get("result") or {}).get("tools") or []
    for t in tools:
        n = t.get("name")
        if n: names.append(n)
print("\n".join(names))
PYEOF
)"

MISSING=()
for tool in "${EXPECTED[@]}"; do
  if ! grep -qx "$tool" <<< "$NAMES"; then
    MISSING+=("$tool")
  fi
done

COUNT="$(printf '%s\n' "$NAMES" | grep -c . || true)"
echo "Tools advertised: $COUNT"
printf '%s\n' "$NAMES" | sed 's/^/  /'

if (( ${#MISSING[@]} == 0 )) && (( COUNT >= 13 )); then
  ok "All 13 expected tools are present."
  exit 0
elif (( ${#MISSING[@]} > 0 )); then
  warn "Missing: ${MISSING[*]}"
  die "Verification failed."
else
  die "Got $COUNT tools (expected ≥ 13)."
fi
