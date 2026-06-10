#!/usr/bin/env bash
# One-shot setup for the drawio MCP server.
# Creates the venv, installs the package in editable mode, and patches
# .vscode/mcp.json so VS Code launches the venv's Python.
# Safe to re-run.

set -euo pipefail

# ---------- color ----------
if [[ -t 1 ]]; then
  C_BOLD=$'\033[1m'; C_RED=$'\033[31m'; C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'; C_BLUE=$'\033[34m'; C_RESET=$'\033[0m'
else
  C_BOLD=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_RESET=""
fi
say()  { printf "%s==>%s %s\n" "$C_BLUE$C_BOLD" "$C_RESET" "$*"; }
ok()   { printf "%s✓%s %s\n" "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf "%s!%s %s\n" "$C_YELLOW" "$C_RESET" "$*"; }
die()  { printf "%s✗%s %s\n" "$C_RED" "$C_RESET" "$*" >&2; exit 1; }

# ---------- paths ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SERVER_DIR="$REPO_ROOT/drawio-mcp-server"
VENV_DIR="$SERVER_DIR/.venv"
MCP_JSON="$REPO_ROOT/.vscode/mcp.json"
SETTINGS_JSON="$REPO_ROOT/.vscode/settings.json"

OS="$(uname -s)"
say "Detected OS: $OS"
say "Repo root:   $REPO_ROOT"

# ---------- 1. python ----------
PY=""
for cand in python3.13 python3.12 python3.11 python3.10 python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
      PY="$cand"; break
    fi
  fi
done

if [[ -z "$PY" ]]; then
  if [[ "$OS" == "Darwin" ]]; then
    die "Python 3.10+ not found. Install with:  brew install python@3.12"
  else
    die "Python 3.10+ not found. Install with:  sudo apt install -y python3.12 python3.12-venv"
  fi
fi
ok "Using $PY ($("$PY" --version))"

# ---------- 2. venv ----------
# Probe for the python BINARY, not just the directory — a previous
# interrupted setup can leave a stub .venv/ with no bin/python in it,
# which would crash the rest of the script with a cryptic error.
VENV_PY="$VENV_DIR/bin/python"
if [[ -x "$VENV_PY" ]]; then
  ok "venv already exists and is healthy at $VENV_DIR"
else
  if [[ -d "$VENV_DIR" ]]; then
    warn "Found incomplete venv at $VENV_DIR — removing and recreating"
    rm -rf "$VENV_DIR"
  fi
  say "Creating venv"
  "$PY" -m venv "$VENV_DIR" || die "venv creation failed (need python3-venv on Debian/Ubuntu)"
  ok "venv created"
fi
[[ -x "$VENV_PY" ]] || die "venv Python still not executable after recreate: $VENV_PY"

# ---------- 3. install ----------
say "Upgrading pip"
"$VENV_PY" -m pip install --quiet --upgrade pip
ok "pip upgraded"

say "Installing drawio-mcp-server (editable) + normalizer extra"
# The [normalizer] extra pulls in the anthropic SDK used by
# scripts/normalize_jira_story.py for the LLM-rewrite path. Pure-Python
# wheel — installs the same way on macOS / Linux / Windows.
"$VENV_PY" -m pip install --quiet -e "$SERVER_DIR[normalizer]"
ok "package installed (with normalizer extra)"

# Python 3.13's site.py SKIPS .pth files whose name starts with an
# underscore ("hidden") — and hatchling's editable install creates
# `_editable_impl_<name>.pth`. Rename it so the package is importable
# without setting PYTHONPATH (pytest, REPL, plain `python -c`).
SITE_DIR="$("$VENV_PY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
for pth in "$SITE_DIR"/_editable_impl_*.pth; do
  [[ -f "$pth" ]] || continue
  new="$SITE_DIR/$(basename "$pth" | sed 's/^_//')"
  if [[ ! -e "$new" ]]; then
    mv "$pth" "$new"
    ok "renamed $(basename "$pth") → $(basename "$new") for Python 3.13 compatibility"
  fi
done

# ---------- 4. patch mcp.json ----------
say "Patching .vscode/mcp.json"
mkdir -p "$REPO_ROOT/.vscode"
"$VENV_PY" - "$MCP_JSON" "$VENV_PY" <<'PYEOF'
import json, os, sys
path, venv_py = sys.argv[1], sys.argv[2]
default = {
  "servers": {
    "drawio": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "drawio_mcp_server"],
      "cwd": "${workspaceFolder}",
      "env": {
        "DRAWIO_DIAGRAMS_DIR": "${workspaceFolder}/diagrams",
        "DRAWIO_STORIES_DIR":  "${workspaceFolder}/jira-stories",
        "PYTHONPATH":          "${workspaceFolder}/drawio-mcp-server/src"
      }
    }
  }
}
data = default
if os.path.exists(path):
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception:
        data = default
data.setdefault("servers", {}).setdefault("drawio", default["servers"]["drawio"])
data["servers"]["drawio"]["command"] = "${workspaceFolder}/drawio-mcp-server/.venv/bin/python"
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print(f"  wrote {path}")
PYEOF
ok ".vscode/mcp.json points at venv Python"

# ---------- 5. ensure settings.json keys ----------
say "Ensuring .vscode/settings.json has required keys"
"$VENV_PY" - "$SETTINGS_JSON" <<'PYEOF'
import json, os, sys
path = sys.argv[1]
required = {
  "files.associations": {"*.drawio": "xml"},
  "github.copilot.chat.codeGeneration.useInstructionFiles": True,
  "chat.mcp.access": "all",
}
data = {}
if os.path.exists(path):
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception:
        data = {}
changed = False
for k, v in required.items():
    if data.get(k) != v:
        data[k] = v
        changed = True
if changed:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print("  updated", path)
else:
    print("  already up to date")
PYEOF
ok "settings.json checked"

# ---------- 6. final hint ----------
echo
ok "Setup complete."
echo "Next steps:"
echo "  1. ${C_BOLD}bash scripts/linux/verify.sh${C_RESET}   — sanity-check the install"
echo "  2. Open this folder in VS Code"
echo "  3. ⇧⌘P / Ctrl+Shift+P → Developer: Reload Window"
echo "  4. Copilot Chat → MCP indicator → confirm 'drawio' is connected (13 tools)"
