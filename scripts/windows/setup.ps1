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

# Continue past errors instead of aborting - we want a best-effort run that does
# as much as it can and reports everything that went wrong at the end.
$ErrorActionPreference = 'Continue'

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[OK] $msg"  -ForegroundColor Green }
function Write-Warn2($msg){ Write-Host "[!]  $msg"  -ForegroundColor Yellow }

# Record a failure and keep going (does NOT exit). Reported in the summary.
# Use a plain PowerShell array rather than New-Object System.Collections.ArrayList:
# locked-down corporate machines often run in Constrained Language Mode, where
# New-Object for arbitrary .NET types is blocked and would leave $Problems null,
# making every Note-Fail call throw "InvokeMethodOnNull". A native array works in
# both full and constrained language modes.
$script:Problems = @()
# Must use $script: on the += so the assignment updates the script-scoped array
# instead of creating a function-local copy.
function Note-Fail($msg) { Write-Host "[X]  $msg" -ForegroundColor Red; $script:Problems += $msg }

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
$ExactPy = $false   # whether the chosen Python must match $ReqVer exactly
if ($Offline) {
    # Match only version-specific wheels (doubled tag, e.g. cp312-cp312); this
    # deliberately ignores stable-ABI wheels like cryptography's cp311-abi3,
    # whose tag does NOT pin the interpreter version.
    $cpTag = Get-ChildItem $WheelsDir -Filter *.whl |
             ForEach-Object { if ($_.Name -match '-cp(3\d{1,2})-cp\1-') { $Matches[1] } } |
             Select-Object -First 1
    if ($cpTag) {
        $ReqVer     = '3.' + $cpTag.Substring(1)          # cp312 -> 312 -> 3.12
        $ReqMajor   = [int]$ReqVer.Split('.')[0]
        $ReqMinor   = [int]$ReqVer.Split('.')[1]
        $candidates = @("py -$ReqVer", 'python', 'python3')
        $ExactPy    = $true
        Write-Step "Offline wheelhouse targets Python $ReqVer (tag cp$cpTag) - requiring an exact match"
    } else {
        # Couldn't read a version-specific tag - still install from the wheelhouse,
        # just don't pin the interpreter version.
        Note-Fail "Offline mode: no version-specific cp3XX-cp3XX wheel found in $WheelsDir - cannot pin the Python version; trying any 3.10+."
        $candidates = @('py -3.13','py -3.12','py -3.11','py -3.10','py -3','python','python3')
    }
} else {
    $candidates = @('py -3.13','py -3.12','py -3.11','py -3.10','py -3','python','python3')
}

$Py = Find-Python $candidates $ExactPy $ReqMajor $ReqMinor

if (-not $Py) {
    if ($ExactPy) {
        Note-Fail "Python $ReqVer not found. The offline wheelhouse needs exactly $ReqVer - install it from https://www.python.org/downloads/ and re-run, or regenerate wheels\ for your installed version (see wheels\README.md)."
    } else {
        Note-Fail "Python 3.10+ not found. Install it from https://www.python.org/downloads/ and re-run."
    }
} else {
    $PyVer = & cmd /c "$Py --version 2>&1"
    Write-Ok "Using $Py ($PyVer)"
}

# ---------- 2. venv ----------
if ($Py) {
    if (Test-Path $VenvPython) {
        Write-Ok "venv already exists at $VenvDir"
    } else {
        Write-Step "Creating venv"
        & cmd /c "$Py -m venv `"$VenvDir`""
        if ($LASTEXITCODE -ne 0)        { Note-Fail "venv creation failed" }
        elseif (Test-Path $VenvPython)  { Write-Ok "venv created" }
    }
}

# $VenvReady gates the package install. It is false if the venv is missing or
# (offline) is the wrong Python version - either way installing would fail.
$VenvReady = Test-Path $VenvPython
if (-not $VenvReady) {
    Note-Fail "venv Python missing: $VenvPython - skipping package install."
} elseif ($ExactPy) {
    # Offline: a venv left over from an earlier run could be the wrong Python.
    $venvVer = (& $VenvPython -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
    if ($venvVer -ne $ReqVer) {
        Note-Fail "Existing venv at $VenvDir is Python $venvVer but the wheelhouse needs $ReqVer. Remove it and re-run: Remove-Item -Recurse -Force `"$VenvDir`""
        $VenvReady = $false
    } else {
        Write-Ok "venv Python $venvVer matches the wheelhouse"
    }
}

# ---------- 3. install ----------
# Each install step records failures but does NOT abort - a failing pip upgrade
# must not stop the package install, and a failing install must not stop the
# VS Code patches below.
if ($VenvReady) {
    Write-Step "Upgrading pip"
    & $VenvPython -m pip install --quiet @PipSrc --upgrade pip
    if ($LASTEXITCODE -ne 0) { Note-Fail "pip upgrade failed (continuing)" }
    else { Write-Ok "pip upgraded" }

    Write-Step "Installing drawio-mcp-server (editable) + normalizer extra"
    # The [normalizer] extra pulls in the anthropic SDK used by
    # scripts\normalize_jira_story.py for the LLM-rewrite path. Pure-Python
    # wheel - installs the same way on macOS / Linux / Windows.
    # In offline mode (@PipSrc = --no-index --find-links wheels) the anthropic
    # SDK and every transitive dep are resolved from the local wheelhouse, and
    # pip's build isolation pulls hatchling/editables from there too.
    & $VenvPython -m pip install --quiet @PipSrc -e "$ServerDir[normalizer]"
    if ($LASTEXITCODE -ne 0) { Note-Fail "pip install -e .[normalizer] failed (continuing)" }
    else { Write-Ok "package installed (with normalizer extra)" }

    # Python 3.13's site.py SKIPS .pth files whose name starts with an
    # underscore ("hidden") - and hatchling's editable install creates
    # `_editable_impl_<name>.pth`. Rename it so the package is importable
    # without setting PYTHONPATH (pytest, REPL, plain `python -c`).
    $SiteDir = & $VenvPython -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"
    Get-ChildItem -Path $SiteDir -Filter "_editable_impl_*.pth" -ErrorAction SilentlyContinue | ForEach-Object {
        $newName = $_.Name -replace '^_', ''
        $newPath = Join-Path $SiteDir $newName
        if (-not (Test-Path $newPath)) {
            Move-Item $_.FullName $newPath -ErrorAction SilentlyContinue
            if (Test-Path $newPath) { Write-Ok "renamed $($_.Name) -> $newName for Python 3.13 compatibility" }
        }
    }
} else {
    Write-Warn2 "Skipping pip install - no usable venv (see errors above)."
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

if (Test-Path $VenvPython) {
    $tmpPy = Join-Path $env:TEMP "patch_mcp_${PID}_$(Get-Random).py"
    Set-Content -Path $tmpPy -Value $patchScript -Encoding UTF8
    try {
        & $VenvPython $tmpPy $McpJson $VenvPython
        if ($LASTEXITCODE -ne 0) { Note-Fail "Failed to patch mcp.json (continuing)" }
        else { Write-Ok ".vscode/mcp.json points at venv Python" }
    } finally {
        Remove-Item $tmpPy -ErrorAction SilentlyContinue
    }
} else {
    Note-Fail "Skipping mcp.json patch - no venv Python at $VenvPython."
}

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
if (Test-Path $VenvPython) {
    $tmpPy2 = Join-Path $env:TEMP "patch_settings_${PID}_$(Get-Random).py"
    Set-Content -Path $tmpPy2 -Value $settingsScript -Encoding UTF8
    try {
        & $VenvPython $tmpPy2 $SettingsJson
        if ($LASTEXITCODE -ne 0) { Note-Fail "Failed to patch settings.json (continuing)" }
        else { Write-Ok "settings.json checked" }
    } finally {
        Remove-Item $tmpPy2 -ErrorAction SilentlyContinue
    }
} else {
    Note-Fail "Skipping settings.json patch - no venv Python at $VenvPython."
}

# ---------- 6. final ----------
Write-Host ""
if ($script:Problems.Count -eq 0) {
    Write-Ok "Setup complete."
} else {
    Write-Warn2 "Setup finished with $($script:Problems.Count) problem(s):"
    foreach ($p in $script:Problems) { Write-Host "       - $p" -ForegroundColor Yellow }
    Write-Host ""
    Write-Host "Fix the above and re-run scripts\windows\setup.ps1 (it is safe to re-run)."
}
Write-Host "Next steps:"
Write-Host "  1. powershell -ExecutionPolicy Bypass -File scripts\windows\verify.ps1"
Write-Host "  2. Open this folder in VS Code"
Write-Host "  3. Ctrl+Shift+P -> Developer: Reload Window"
Write-Host "  4. Copilot Chat -> MCP indicator -> confirm 'drawio' connected (13 tools)"

# Non-zero exit if anything failed, so callers/CI can detect it - but only AFTER
# attempting every step.
if ($script:Problems.Count -gt 0) { exit 1 }
