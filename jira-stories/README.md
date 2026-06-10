# Jira stories — input folder

Drop your raw business-requirement files here, one per Jira ticket:

```
jira-stories/<KEY>.txt
```

Example: `jira-stories/PROJ-127.txt`.

The framework accepts **any plain-text format** — copy-paste from Jira,
Confluence, or just write the requirement in your own words. No
schema needed at this stage.

## Then normalize

Run the normalizer to produce the technical document that the diagram
builder consumes:

```bash
# Linux / macOS
./scripts/linux/normalize.sh <KEY>

# Windows
powershell -ExecutionPolicy Bypass -File scripts\windows\normalize.ps1 <KEY>
```

Output: `jira-stories/<KEY>-surgical.txt` — a 10-section structured
technical document that lists components, interactions, data,
non-functional requirements, and observability.

That `-surgical.txt` is what Copilot Chat reads when you run
`prompts/create-diagram.md`.

## File-name convention

| Pattern | Role |
|---|---|
| `<KEY>.txt` | Raw business requirement (you write this) |
| `<KEY>-surgical.txt` | Normalized technical document (the normalizer writes this) |
| `<KEY>-connectors.md` | 14-column connector-detail table (generate_connector_details.py writes this) |
