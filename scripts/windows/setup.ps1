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

# Return the first candidate launcher that satisfies the version test, else $null.
# $Exact=$true demands major.minor == ($Maj,$Min); otherwise just >= 3.10.
function Find-Python([string[]]$Cands, [bool]$Exact, [int]$Maj, [int]$Min) {
    foreach ($cand in $Cands) {
        try {
            if ($Exact) {
                $check = "import sys; raise SystemExit(0 if sys.version_info[:2] == ($Maj,$Min) else 1)"
            } else {
                $check = "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
            }
            $null = & cmd /c "$cand -c ""$check"" 2>NUL"
            if ($LASTEXITCODE -eq 0) { return $cand }
        } catch { }
    }
    return $null
}

# ---------- paths ----------
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot    = (Resolve-Path (Join-Path $ScriptDir '..\..')).Path
$ServerDir   = Join-Path $RepoRoot 'drawio-mcp-server'
$VenvDir     = Join-Path $ServerDir '.venv'
$VenvPython  = Join-Path $VenvDir 'Scripts\python.exe'
$McpJson     = Join-Path $RepoRoot '.vscode\mcp.json'
$SettingsJson= Join-Path $RepoRoot '.vscode\settings.json'
$WheelsDir   = Join-Path $RepoRoot 'wheels'

Write-Step "Repo root: $RepoRoot"

# ---------- offline mode ----------
# If a populated wheels\ folder is present (e.g. the corporate network blocks
# PyPI), install everything from there instead of downloading. The wheelhouse
# must contain win_amd64 / cp312 wheels - see wheels\README.md.
$Offline = (Test-Path $WheelsDir) -and (@(Get-ChildItem $WheelsDir -Filter *.whl -ErrorAction SilentlyContinue).Count -gt 0)
if ($Offline) {
    Write-Ok "Offline wheelhouse detected: $WheelsDir (PyPI not required)"
    $PipSrc = @('--no-index', "--find-links", $WheelsDir)
} else {
    $PipSrc = @()
}

# ---------- 1. python ----------
# Offline mode: the wheelhouse is built for ONE CPython version (the cp3XX tag
# on the compiled wheels, e.g. pydantic_core / jiter). Installing into any other
# version fails later with a confusing "no matching distribution" error, so we
# detect the required version from the wheel filenames and demand an EXACT match
# up front. Online mode keeps the original "highest 3.10+ wins" behaviour.
if ($Offline) {
    # Match only version-specific wheels (doubled tag, e.g. cp312-cp312); this
    # deliberately ignores stable-ABI wheels like cryptography's cp311-abi3,
    # whose tag does NOT pin the interpreter version.
    $cpTag = Get-ChildItem $WheelsDir -Filter *.whl |
             ForEach-Object { if ($_.Name -match '-cp(3\d{1,2})-cp\1-') { $Matches[1] } } |
             Select-Object -First 1
    if (-not $cpTag) { Die "Offline mode: no version-specific cp3XX-cp3XX wheel found in $WheelsDir - cannot determine the required Python version." }
    $ReqVer     = '3.' + $cpTag.Substring(1)          # cp312 -> 312 -> 3.12
    $ReqMajor   = [int]$ReqVer.Split('.')[0]
    $ReqMinor   = [int]$ReqVer.Split('.')[1]
    $candidates = @("py -$ReqVer", 'python', 'python3')
    Write-Step "Offline wheelhouse targets Python $ReqVer (tag cp$cpTag) - requiring an exact match"
} else {
    $candidates = @('py -3.13','py -3.12','py -3.11','py -3.10','py -3','python','python3')
}

$Py = Find-Python $candidates $Offline $ReqMajor $ReqMinor

# Offline: if the exact required Python is missing, try to install it with winget
# before giving up. winget pulls from Microsoft's CDN (not PyPI), so it usually
# works even on a network that blocks PyPI. The py launcher picks up the new
# install via the registry, so no shell restart is needed in the same session.
if (-not $Py -and $Offline) {
    Write-Warn2 "Python $ReqVer not found - attempting automatic install via winget"
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Die "winget is not available on this machine, so Python $ReqVer cannot be auto-installed. Install it manually from https://www.python.org/downloads/ (or via your software center) and re-run, or regenerate wheels\ for your installed version - see wheels\README.md."
    }
    Write-Step "winget install --exact --id Python.Python.$ReqVer"
    & winget install --exact --id "Python.Python.$ReqVer" --source winget --scope user `
        --accept-source-agreements --accept-package-agreements --silent
    # winget returns non-zero for benign cases too (e.g. already installed); don't
    # trust the code - just re-probe for a usable interpreter.
    if ($LASTEXITCODE -ne 0) { Write-Warn2 "winget exit code $LASTEXITCODE - re-checking for Python anyway" }
    # winget added Python to PATH, but THIS process captured its PATH at launch and
    # won't see the new entries. Refresh from the registry and also probe the
    # default per-user install path directly, so the re-check succeeds without
    # having to reopen PowerShell.
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' +
                [System.Environment]::GetEnvironmentVariable('Path','User')
    $directPy = Join-Path $env:LOCALAPPDATA "Programs\Python\Python$ReqMajor$ReqMinor\python.exe"
    $probe = if (Test-Path $directPy) { @("`"$directPy`"") + $candidates } else { $candidates }
    $Py = Find-Python $probe $Offline $ReqMajor $ReqMinor
    if ($Py) { Write-Ok "Python $ReqVer installed via winget" }
}

if (-not $Py) {
    if ($Offline) {
        Die "Python $ReqVer still not found after the winget attempt. Install it manually (https://www.python.org/downloads/) and re-run, or regenerate wheels\ for your installed version - see wheels\README.md."
    } else {
        Die "Python 3.10+ not found. Install: winget install Python.Python.3.12"
    }
}
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

# Offline: a venv left over from an earlier run could be the wrong Python.
# Verify it matches the wheelhouse before we try to install into it.
if ($Offline) {
    $venvVer = (& $VenvPython -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
    if ($venvVer -ne $ReqVer) {
        Die "Existing venv at $VenvDir is Python $venvVer but the wheelhouse needs $ReqVer. Remove it and re-run: Remove-Item -Recurse -Force `"$VenvDir`""
    }
    Write-Ok "venv Python $venvVer matches the wheelhouse"
}

# ---------- 3. install ----------
Write-Step "Upgrading pip"
& $VenvPython -m pip install --quiet @PipSrc --upgrade pip
if ($LASTEXITCODE -ne 0) { Die "pip upgrade failed" }
Write-Ok "pip upgraded"

Write-Step "Installing drawio-mcp-server (editable) + normalizer extra"
# The [normalizer] extra pulls in the anthropic SDK used by
# scripts\normalize_jira_story.py for the LLM-rewrite path. Pure-Python
# wheel - installs the same way on macOS / Linux / Windows.
# In offline mode (@PipSrc = --no-index --find-links wheels) the anthropic
# SDK and every transitive dep are resolved from the local wheelhouse, and
# pip's build isolation pulls hatchling/editables from there too.
& $VenvPython -m pip install --quiet @PipSrc -e "$ServerDir[normalizer]"
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
