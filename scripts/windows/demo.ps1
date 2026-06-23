<#
.SYNOPSIS
  Drop the bundled sample story into jira-stories\DEMO-001.txt.
.DESCRIPTION
  We deliberately use DEMO-001 (not PROJ-123) because
  jira-stories\PROJ-123.txt is the canonical worked-example story the
  docs and prompts point at - overwriting it would invalidate those
  references.
#>
$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = (Resolve-Path (Join-Path $ScriptDir '..\..')).Path
$Src       = Join-Path $RepoRoot 'examples\sample-jira-story.txt'
$Dst       = Join-Path $RepoRoot 'jira-stories\DEMO-001.txt'

if (-not (Test-Path $Src)) {
    Write-Host "[X] Missing $Src - repo seems incomplete." -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path (Split-Path $Dst) | Out-Null

if ((Test-Path $Dst) -and ((Get-FileHash $Src).Hash -ne (Get-FileHash $Dst).Hash)) {
    Write-Host "Refusing to overwrite an existing $Dst that differs from the sample."
    Write-Host "Delete it first if you want to reset:  Remove-Item `"$Dst`""
    exit 1
}

Copy-Item -Force $Src $Dst
Write-Host "Wrote $Dst"
Write-Host ""
Write-Host "Now in VS Code Copilot Chat, paste:"
Write-Host ""
Write-Host "@workspace Use the prompt at prompts/create-diagram.md."
Write-Host "The story is jira-stories/DEMO-001.txt."
Write-Host "Save the diagram as diagrams/demo-001.drawio."
Write-Host ""
