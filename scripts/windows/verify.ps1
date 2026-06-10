<#
.SYNOPSIS
  Sanity-check the MCP server: send tools/list and confirm 13 tools.
#>
$ErrorActionPreference = 'Stop'

function Write-Ok($m){ Write-Host "[OK] $m" -ForegroundColor Green }
function Write-Warn2($m){ Write-Host "[!]  $m" -ForegroundColor Yellow }
function Die($m){ Write-Host "[X]  $m" -ForegroundColor Red; exit 1 }

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot   = (Resolve-Path (Join-Path $ScriptDir '..\..')).Path
$VenvPython = Join-Path $RepoRoot 'drawio-mcp-server\.venv\Scripts\python.exe'

if (-not (Test-Path $VenvPython)) {
    Die "venv Python missing at $VenvPython - run scripts\windows\setup.ps1 first"
}

$expected = @(
    'list_diagrams','read_diagram','read_diagram_summary','create_diagram',
    'add_container','add_node','add_edge','add_title','add_connector_table',
    'update_node','remove_element',
    'list_stories','read_story'
)

$init   = '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"verify.ps1","version":"1.0"}}}'
$inited = '{"jsonrpc":"2.0","method":"notifications/initialized"}'
$list   = '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
$payload = "$init`n$inited`n$list`n"

$env:DRAWIO_DIAGRAMS_DIR = (Join-Path $RepoRoot 'diagrams')
$env:DRAWIO_STORIES_DIR  = (Join-Path $RepoRoot 'jira-stories')
$env:PYTHONPATH          = (Join-Path $RepoRoot 'drawio-mcp-server\src')

$tmpIn = Join-Path $env:TEMP "mcp_probe_$([guid]::NewGuid().ToString('N')).jsonl"
Set-Content -Path $tmpIn -Value $payload -Encoding ASCII

try {
    $out = & cmd /c "type `"$tmpIn`" | `"$VenvPython`" -m drawio_mcp_server 2>nul"
} finally {
    Remove-Item $tmpIn -ErrorAction SilentlyContinue
}

if ([string]::IsNullOrWhiteSpace($out)) {
    Die "Server produced no output. Run scripts\windows\run-server.ps1 to see errors."
}

$parseScript = @'
import json, sys
buf = sys.stdin.read()
names = []
for line in buf.splitlines():
    line = line.strip()
    if not line: continue
    try: msg = json.loads(line)
    except Exception: continue
    tools = (msg.get("result") or {}).get("tools") or []
    for t in tools:
        n = t.get("name")
        if n: names.append(n)
print("\n".join(names))
'@
$tmpPy = Join-Path $env:TEMP "parse_$([guid]::NewGuid().ToString('N')).py"
Set-Content -Path $tmpPy -Value $parseScript -Encoding UTF8
try {
    $names = $out | & $VenvPython $tmpPy
} finally {
    Remove-Item $tmpPy -ErrorAction SilentlyContinue
}

$nameList = $names -split "`n" | Where-Object { $_ -and $_.Trim() -ne '' } | ForEach-Object { $_.Trim() }
$count = $nameList.Count

Write-Host "Tools advertised: $count"
$nameList | ForEach-Object { Write-Host "  $_" }

$missing = @()
foreach ($t in $expected) { if ($nameList -notcontains $t) { $missing += $t } }

if ($missing.Count -eq 0 -and $count -ge 13) {
    Write-Ok "All 13 expected tools are present."
    exit 0
} elseif ($missing.Count -gt 0) {
    Write-Warn2 ("Missing: " + ($missing -join ', '))
    Die "Verification failed."
} else {
    Die "Got $count tools (expected >= 13)."
}
