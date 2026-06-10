<#
.SYNOPSIS
  Cross-OS-friendly wrapper around scripts\normalize_jira_story.py.
.DESCRIPTION
  Locates the project venv created by scripts\windows\setup.ps1 and
  invokes the normalizer with all forwarded arguments.

  Usage:
    .\scripts\windows\normalize.ps1 jira-stories\PROJ-124.txt
    .\scripts\windows\normalize.ps1 jira-stories\PROJ-124.txt --diagram PROJ-123-20260524-045255.drawio
    .\scripts\windows\normalize.ps1 jira-stories\PROJ-124.txt --check

  Identical behavior to scripts\mac\normalize.sh and
  scripts\linux\normalize.sh - the only difference is venv layout
  (Scripts\python.exe vs bin/python).
#>
$ErrorActionPreference = 'Stop'

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot   = (Resolve-Path (Join-Path $ScriptDir '..\..')).Path
$VenvPython = Join-Path $RepoRoot 'drawio-mcp-server\.venv\Scripts\python.exe'
$Normalizer = Join-Path $RepoRoot 'scripts\normalize_jira_story.py'

if (-not (Test-Path $VenvPython)) {
    Write-Host "[X] venv Python missing at $VenvPython - run scripts\windows\setup.ps1 first" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $Normalizer)) {
    Write-Host "[X] normalizer script missing at $Normalizer" -ForegroundColor Red
    exit 1
}

& $VenvPython $Normalizer @args
exit $LASTEXITCODE
