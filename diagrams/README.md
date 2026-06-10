# Diagrams — output folder

Generated `.drawio` files land here. Filenames are timestamp-suffixed
so you never overwrite an earlier run:

```
diagrams/<KEY>-<YYYYMMDD>-<HHMMSS>.drawio
```

Open them in the **draw.io VS Code extension**
(`hediet.vscode-drawio`) or any draw.io / diagrams.net client.

## What ships in a diagram

| Layer | What you see |
|---|---|
| Swimlanes | 4–6 colour-coded vertical columns (External, Ingestion, Processing, …) — 140 px gap between them |
| Icons | Official service icons (e.g. GCP) at 64 × 64 inside each swimlane |
| Connectors | Numbered, routed, fanned-out, with `N. <label>` prefix in Google-blue bold above the line |
| Busy-node cards | Icons with > 3 connectors auto-wrap in a thin rounded border |
| Title | Optional bold deck-quality banner above the swimlanes |
| Connector-detail table | 14 columns × N rows below the swimlanes — one row per numbered connector |

## Retrofit an existing diagram

If a layout-related code change lands after a diagram was created,
re-run the routing passes without re-asking Copilot:

```bash
python scripts/reroute_diagram.py <KEY>-<timestamp>.drawio
```

This re-computes container positions, child stride, edge waypoints,
sub-lane deconfliction, and busy-node framing — and writes a new
timestamped file alongside the original (`.bak` left of the input).
