<#
.SYNOPSIS
  Run the MCP server in the foreground (stdio) for debugging.
.DESCRIPTION
  The server blocks on stdin waiting for JSON-RPC. Use Ctrl+C to stop.
#>
$ErrorActionPreference = 'Stop'

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot   = (Resolve-Path (Join-Path $ScriptDir '..\..')).Path
$VenvPython = Join-Path $RepoRoot 'drawio-mcp-server\.venv\Scripts\python.exe'

if (-not (Test-Path $VenvPython)) {
    Write-Host "[X] venv Python missing at $VenvPython - run scripts\windows\setup.ps1 first" -ForegroundColor Red
    exit 1
}

$env:DRAWIO_DIAGRAMS_DIR = (Join-Path $RepoRoot 'diagrams')
$env:DRAWIO_STORIES_DIR  = (Join-Path $RepoRoot 'jira-stories')
$env:PYTHONPATH          = (Join-Path $RepoRoot 'drawio-mcp-server\src')
$env:PYTHONFAULTHANDLER  = '1'

Write-Host "Launching drawio MCP server (Ctrl+C to stop)"
Write-Host "  DRAWIO_DIAGRAMS_DIR = $($env:DRAWIO_DIAGRAMS_DIR)"
Write-Host "  DRAWIO_STORIES_DIR  = $($env:DRAWIO_STORIES_DIR)"
Write-Host ""

& $VenvPython -m drawio_mcp_server
exit $LASTEXITCODE
