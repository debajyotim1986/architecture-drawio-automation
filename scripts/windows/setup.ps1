<#
.SYNOPSIS
  One-shot setup for the drawio MCP server on Windows.
.DESCRIPTION
  Creates the venv, installs the package in editable mode, and patches
  .vscode/mcp.json so VS Code launches the venv's Python.
  Safe to re-run.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1
#>

$ErrorActionPreference = 'Stop'

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[OK] $msg"  -ForegroundColor Green }
function Write-Warn2($msg){ Write-Host "[!]  $msg"  -ForegroundColor Yellow }
function Die($msg) { Write-Host "[X]  $msg" -ForegroundColor Red; exit 1 }

# ---------- paths ----------
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot    = (Resolve-Path (Join-Path $ScriptDir '..\..')).Path
$ServerDir   = Join-Path $RepoRoot 'drawio-mcp-server'
$VenvDir     = Join-Path $ServerDir '.venv'
$VenvPython  = Join-Path $VenvDir 'Scripts\python.exe'
$McpJson     = Join-Path $RepoRoot '.vscode\mcp.json'
$SettingsJson= Join-Path $RepoRoot '.vscode\settings.json'

Write-Step "Repo root: $RepoRoot"

# ---------- 1. python ----------
$Py = $null
foreach ($cand in @('py -3.13','py -3.12','py -3.11','py -3.10','py -3','python','python3')) {
    try {
        $verOk = & cmd /c "$cand -c ""import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"" 2>NUL"
        if ($LASTEXITCODE -eq 0) { $Py = $cand; break }
    } catch { }
}
if (-not $Py) { Die "Python 3.10+ not found. Install: winget install Python.Python.3.12" }
$PyVer = & cmd /c "$Py --version 2>&1"
Write-Ok "Using $Py ($PyVer)"

# ---------- 2. venv ----------
if (Test-Path $VenvPython) {
    Write-Ok "venv already exists at $VenvDir"
} else {
    Write-Step "Creating venv"
    & cmd /c "$Py -m venv `"$VenvDir`""
    if ($LASTEXITCODE -ne 0) { Die "venv creation failed" }
    Write-Ok "venv created"
}
if (-not (Test-Path $VenvPython)) { Die "venv Python missing: $VenvPython" }

# ---------- 3. install ----------
Write-Step "Upgrading pip"
& $VenvPython -m pip install --quiet --upgrade pip
if ($LASTEXITCODE -ne 0) { Die "pip upgrade failed" }
Write-Ok "pip upgraded"

Write-Step "Installing drawio-mcp-server (editable) + normalizer extra"
# The [normalizer] extra pulls in the anthropic SDK used by
# scripts\normalize_jira_story.py for the LLM-rewrite path. Pure-Python
# wheel - installs the same way on macOS / Linux / Windows.
& $VenvPython -m pip install --quiet -e "$ServerDir[normalizer]"
if ($LASTEXITCODE -ne 0) { Die "pip install -e .[normalizer] failed" }
Write-Ok "package installed (with normalizer extra)"

# Python 3.13's site.py SKIPS .pth files whose name starts with an
# underscore ("hidden") - and hatchling's editable install creates
# `_editable_impl_<name>.pth`. Rename it so the package is importable
# without setting PYTHONPATH (pytest, REPL, plain `python -c`).
$SiteDir = & $VenvPython -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"
Get-ChildItem -Path $SiteDir -Filter "_editable_impl_*.pth" -ErrorAction SilentlyContinue | ForEach-Object {
    $newName = $_.Name -replace '^_', ''
    $newPath = Join-Path $SiteDir $newName
    if (-not (Test-Path $newPath)) {
        Move-Item $_.FullName $newPath
        Write-Ok "renamed $($_.Name) -> $newName for Python 3.13 compatibility"
    }
}

# ---------- 4. patch mcp.json ----------
Write-Step "Patching .vscode/mcp.json"
New-Item -ItemType Directory -Force -Path (Split-Path $McpJson) | Out-Null

$patchScript = @'
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
data["servers"]["drawio"]["command"] = "${workspaceFolder}/drawio-mcp-server/.venv/Scripts/python.exe"
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print(f"  wrote {path}")
'@

$tmpPy = Join-Path $env:TEMP "patch_mcp_$([guid]::NewGuid().ToString('N')).py"
Set-Content -Path $tmpPy -Value $patchScript -Encoding UTF8
try {
    & $VenvPython $tmpPy $McpJson $VenvPython
    if ($LASTEXITCODE -ne 0) { Die "Failed to patch mcp.json" }
} finally {
    Remove-Item $tmpPy -ErrorAction SilentlyContinue
}
Write-Ok ".vscode/mcp.json points at venv Python"

# ---------- 5. settings.json ----------
Write-Step "Ensuring .vscode/settings.json has required keys"
$settingsScript = @'
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
'@
$tmpPy2 = Join-Path $env:TEMP "patch_settings_$([guid]::NewGuid().ToString('N')).py"
Set-Content -Path $tmpPy2 -Value $settingsScript -Encoding UTF8
try {
    & $VenvPython $tmpPy2 $SettingsJson
} finally {
    Remove-Item $tmpPy2 -ErrorAction SilentlyContinue
}
Write-Ok "settings.json checked"

# ---------- 6. final ----------
Write-Host ""
Write-Ok "Setup complete."
Write-Host "Next steps:"
Write-Host "  1. powershell -ExecutionPolicy Bypass -File scripts\windows\verify.ps1"
Write-Host "  2. Open this folder in VS Code"
Write-Host "  3. Ctrl+Shift+P -> Developer: Reload Window"
Write-Host "  4. Copilot Chat -> MCP indicator -> confirm 'drawio' connected (13 tools)"
