<#
.SYNOPSIS
  Remove the venv (and optionally generated artifacts).
.PARAMETER All
  Also remove the demo story (jira-stories\DEMO-001.*) and any
  *.drawio files generated under diagrams\. Note: PROJ-123.txt is the
  canonical worked-example story and is NEVER removed.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\windows\clean.ps1
  powershell -ExecutionPolicy Bypass -File scripts\windows\clean.ps1 -All
#>
param(
    [switch]$All
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = (Resolve-Path (Join-Path $ScriptDir '..\..')).Path
$VenvDir   = Join-Path $RepoRoot 'drawio-mcp-server\.venv'
$ServerDir = Join-Path $RepoRoot 'drawio-mcp-server'

if (Test-Path $VenvDir) {
    Write-Host "Removing $VenvDir"
    Remove-Item -Recurse -Force $VenvDir
} else {
    Write-Host "venv already absent"
}

# Pycache / build artifacts
Get-ChildItem -Path $ServerDir -Recurse -Force -ErrorAction SilentlyContinue `
  | Where-Object { $_.PSIsContainer -and ($_.Name -in '__pycache__','.pytest_cache' -or $_.Name -like '*.egg-info') } `
  | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

if ($All) {
    Write-Host "-All: also removing jira-stories\DEMO-001.* and diagrams\*.drawio"
    # PROJ-123.txt is the canonical worked-example story (the
    # normalizer's template lives at template\surgical-story-template.txt)
    # - NEVER delete it; the docs and prompts point at it.
    Remove-Item -Force (Join-Path $RepoRoot 'jira-stories\DEMO-001.txt') -ErrorAction SilentlyContinue
    Remove-Item -Force (Join-Path $RepoRoot 'jira-stories\DEMO-001-surgical.txt') -ErrorAction SilentlyContinue
    Remove-Item -Force (Join-Path $RepoRoot 'jira-stories\DEMO-001-connectors.md') -ErrorAction SilentlyContinue
    Get-ChildItem -Path (Join-Path $RepoRoot 'diagrams') -Filter *.drawio -File -ErrorAction SilentlyContinue `
      | Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path (Join-Path $RepoRoot 'diagrams') -Filter *.drawio.bak -File -ErrorAction SilentlyContinue `
      | Remove-Item -Force -ErrorAction SilentlyContinue
}

Write-Host "Clean complete."
