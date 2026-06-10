#!/usr/bin/env bash
# One-shot installer + setup for the drawio MCP server on macOS.
#
# What this single script does, end-to-end:
#   1. Installs Homebrew if missing.
#   2. Installs Python 3.12 (>=3.10) via Homebrew if a suitable interpreter
#      isn't already on PATH.
#   3. Installs Git via Homebrew if missing.
#   4. Optionally installs VS Code (cask) and the Copilot + Copilot Chat
#      extensions if the `code` CLI is available.
#   5. Creates the project venv, upgrades pip, installs drawio-mcp-server
#      in editable mode (this is the MCP server install).
#   6. Patches .vscode/mcp.json so VS Code launches the venv's Python.
#   7. Ensures .vscode/settings.json has the keys MCP/Copilot needs.
#
# Safe to re-run. Designed for both Apple Silicon and Intel Macs.
#
# Usage:
#   bash scripts/mac/setup.sh                  # full install + setup
#   bash scripts/mac/setup.sh --skip-prereqs   # skip Homebrew/Python/Git step
#   bash scripts/mac/setup.sh --skip-vscode    # don't try to install VS Code
#   bash scripts/mac/setup.sh --with-extensions  # also install Copilot exts via `code`
#   bash scripts/mac/setup.sh --yes            # non-interactive (assume yes)

set -euo pipefail

# ---------- args ----------
SKIP_PREREQS=false
SKIP_VSCODE=false
WITH_EXTENSIONS=false
ASSUME_YES=false
for arg in "$@"; do
  case "$arg" in
    --skip-prereqs)    SKIP_PREREQS=true ;;
    --skip-vscode)     SKIP_VSCODE=true ;;
    --with-extensions) WITH_EXTENSIONS=true ;;
    --yes|-y)          ASSUME_YES=true ;;
    -h|--help)
      sed -n '2,22p' "$0"; exit 0 ;;
    *)
      echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

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

confirm() {
  $ASSUME_YES && return 0
  local prompt="$1"
  read -r -p "$prompt [Y/n] " ans
  [[ -z "$ans" || "$ans" =~ ^[Yy]$ ]]
}

# ---------- guardrails ----------
if [[ "$(uname -s)" != "Darwin" ]]; then
  die "This script is for macOS. Use scripts/linux/setup.sh on Linux or scripts/windows/setup.ps1 on Windows."
fi

# Force UTF-8 so the glyphs in the printf format strings render correctly
# even when the user has LC_ALL=C or a stripped-down locale.
export LC_ALL="${LC_ALL:-en_US.UTF-8}"
export LANG="${LANG:-en_US.UTF-8}"

# ---------- paths ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SERVER_DIR="$REPO_ROOT/drawio-mcp-server"
VENV_DIR="$SERVER_DIR/.venv"
MCP_JSON="$REPO_ROOT/.vscode/mcp.json"
SETTINGS_JSON="$REPO_ROOT/.vscode/settings.json"

ARCH="$(uname -m)"
say "macOS $(sw_vers -productVersion 2>/dev/null || echo "?") on $ARCH"
say "Repo root: $REPO_ROOT"

# ---------- 1. Homebrew + system prereqs ----------
ensure_brew_on_path() {
  # Apple Silicon: /opt/homebrew/bin; Intel: /usr/local/bin
  if ! command -v brew >/dev/null 2>&1; then
    if [[ -x /opt/homebrew/bin/brew ]]; then
      eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -x /usr/local/bin/brew ]]; then
      eval "$(/usr/local/bin/brew shellenv)"
    fi
  fi
}

install_brew() {
  say "Installing Homebrew"
  if ! confirm "Homebrew not found. Install it now? (requires sudo password)"; then
    die "Cannot continue without Homebrew. Re-run with --skip-prereqs after installing manually."
  fi
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  ensure_brew_on_path
  command -v brew >/dev/null 2>&1 || die "Homebrew install reported success but 'brew' is still not on PATH."
  ok "Homebrew installed"
}

install_brew_pkg() {
  local pkg="$1"
  say "Installing $pkg via Homebrew"
  brew install "$pkg"
  ok "$pkg installed"
}

if ! $SKIP_PREREQS; then
  ensure_brew_on_path
  if ! command -v brew >/dev/null 2>&1; then
    install_brew
  else
    ok "Homebrew present ($(brew --version | head -n1))"
  fi
else
  warn "--skip-prereqs: not installing Homebrew/Python/Git/VS Code"
fi

# ---------- 2. Python 3.10+ ----------
find_python() {
  local cand
  for cand in python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then
      if "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
        echo "$cand"; return 0
      fi
    fi
  done
  return 1
}

PY="$(find_python || true)"
if [[ -z "$PY" ]]; then
  if $SKIP_PREREQS; then
    die "Python 3.10+ not found. Install with: brew install python@3.12 (or rerun without --skip-prereqs)."
  fi
  install_brew_pkg python@3.12
  ensure_brew_on_path
  PY="$(find_python || true)"
  [[ -n "$PY" ]] || die "Python install completed but a usable interpreter still isn't on PATH."
fi
ok "Using $PY ($("$PY" --version 2>&1))"

# ---------- 3. Git ----------
if ! $SKIP_PREREQS; then
  if command -v git >/dev/null 2>&1; then
    ok "Git present ($(git --version))"
  else
    install_brew_pkg git
  fi
fi

# ---------- 4. VS Code (optional) ----------
if ! $SKIP_PREREQS && ! $SKIP_VSCODE; then
  if command -v code >/dev/null 2>&1; then
    ok "VS Code 'code' CLI present"
  elif [[ -d "/Applications/Visual Studio Code.app" ]]; then
    ok "VS Code installed (CLI not on PATH — in VS Code: ⇧⌘P → Shell Command: Install 'code' command in PATH)"
  else
    say "Installing Visual Studio Code (cask)"
    if confirm "Install VS Code via Homebrew cask?"; then
      brew install --cask visual-studio-code || warn "VS Code cask install failed — install it manually from https://code.visualstudio.com/"
    else
      warn "Skipping VS Code install. Install it manually before using Copilot Chat."
    fi
  fi

  if $WITH_EXTENSIONS; then
    if command -v code >/dev/null 2>&1; then
      say "Installing GitHub Copilot extensions"
      code --install-extension GitHub.copilot --force >/dev/null
      code --install-extension GitHub.copilot-chat --force >/dev/null
      ok "Copilot + Copilot Chat extensions installed"
    else
      warn "--with-extensions requested but 'code' CLI not on PATH — skipped. Install via VS Code: ⇧⌘P → Shell Command: Install 'code' command in PATH"
    fi
  fi
fi

# ---------- 5. venv ----------
# Probe for the python BINARY, not just the directory — a previous
# interrupted setup can leave a stub .venv/ with no bin/python in it.
VENV_PY="$VENV_DIR/bin/python"
if [[ -x "$VENV_PY" ]]; then
  ok "venv already exists and is healthy at $VENV_DIR"
else
  if [[ -d "$VENV_DIR" ]]; then
    warn "Found incomplete venv at $VENV_DIR — removing and recreating"
    rm -rf "$VENV_DIR"
  fi
  say "Creating venv at $VENV_DIR"
  "$PY" -m venv "$VENV_DIR" || die "venv creation failed"
  ok "venv created"
fi
[[ -x "$VENV_PY" ]] || die "venv Python still not executable after recreate: $VENV_PY"

# Clear quarantine attribute that Gatekeeper sometimes adds to venv binaries
xattr -dr com.apple.quarantine "$VENV_DIR" 2>/dev/null || true

# ---------- 6. Install MCP server (editable) ----------
say "Upgrading pip in venv"
"$VENV_PY" -m pip install --quiet --upgrade pip
ok "pip upgraded"

say "Installing drawio-mcp-server (editable) + normalizer extra — this is the MCP server"
# The [normalizer] extra pulls in the anthropic SDK used by
# scripts/normalize_jira_story.py for the LLM-rewrite path. Pure-Python
# wheel — installs the same way on macOS / Linux / Windows.
"$VENV_PY" -m pip install --quiet -e "$SERVER_DIR[normalizer]"
ok "MCP server installed (with normalizer extra)"

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

# ---------- 7. Patch .vscode/mcp.json ----------
say "Patching .vscode/mcp.json to use the venv's Python"
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

# ---------- 8. Ensure .vscode/settings.json ----------
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

# ---------- 9. Done ----------
echo
ok "Setup complete."
echo "Next steps:"
echo "  1. ${C_BOLD}bash scripts/mac/verify.sh${C_RESET}   — sanity-check the install"
echo "  2. Open this folder in VS Code (e.g. ${C_BOLD}code \"$REPO_ROOT\"${C_RESET})"
echo "  3. ⇧⌘P → Developer: Reload Window"
echo "  4. Copilot Chat → MCP indicator → confirm 'drawio' is connected (13 tools)"
