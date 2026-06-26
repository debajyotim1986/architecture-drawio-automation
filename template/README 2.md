# Templates

Ready-to-use starting points for the Jira → draw.io architecture-diagram flow.
Copy, fill the placeholders, and go.

| File | What it is | How to use |
|---|---|---|
| [jira-story-template.txt](jira-story-template.txt) | **The raw Jira story template** — the *input* shape, i.e. what a business stakeholder actually hands over: a thin, partial note (often only sections 1-4), with free-form prose in section 3 and a possibly-stale header. The normalizer cleans this up. | Copy to `jira-stories/<KEY>.txt`, rewrite section 3 to describe your pipeline (name components + connections), then run a create/update prompt. Don't worry about polishing — the normalizer turns it into the surgical text. |
| [surgical-story-template.txt](surgical-story-template.txt) | **The canonical surgical-text template** — the *output* shape: the exact form of `jira-stories/<KEY>-surgical.txt`, and the reference template the normalizer (`scripts/normalize_jira_story.py`, `DEFAULT_TEMPLATE`) rewrites raw notes into. Sections 1-11; section 3 (In Scope) drives the diagram. | Usually produced automatically by the normalizer. Edit by hand only if you want full control over the canonical story. |
| [create-single-jira-prompt-template.md](create-single-jira-prompt-template.md) | Prompt for building **one new** diagram from **one** story. | Paste the fenced block into Copilot Chat, replace `{{STORY_FILE}}`. |
| [create-multi-jira-prompt-template.md](create-multi-jira-prompt-template.md) | Prompt for merging **several** stories into **one new** diagram — every story in `jira-stories/` (Option A) or an explicit list (Option B). | Paste the relevant fenced block into Copilot Chat. |
| [update-single-jira-prompt-template.md](update-single-jira-prompt-template.md) | Prompt for patching an **existing** diagram from **one** story (in place, layout preserved). | Paste the fenced block, replace `{{STORY_FILE}}` and `{{DIAGRAM_FILE}}`. |
| [update-multi-jira-prompt-template.md](update-multi-jira-prompt-template.md) | Prompt for applying **several** stories to **one existing** diagram in place — every story (Option A) or an explicit list (Option B). | Paste the relevant fenced block, replace `{{DIAGRAM_FILE}}`. |

**Create vs. update:** use a *create* template when no diagram covers the area
yet; use an *update* template when a diagram already exists and you want to
patch it (update prompts run in diagram-aware "surgical" mode and preserve your
manual layout).

These are trimmed, paste-ready versions. The full reference prompts (with
rationale and the stylish-output checklist) live in
[`../prompts/create-diagram.md`](../prompts/create-diagram.md) and
[`../prompts/update-diagram.md`](../prompts/update-diagram.md). The canonical
worked example is [`../jira-stories/PROJ-123.txt`](../jira-stories/PROJ-123.txt).

> Prerequisite: the `drawio` MCP server must be running, and the scripts
> referenced in the prompts (`normalize_jira_story.py`,
> `generate_connector_details.py`, `verify_mcp.py`) self-bootstrap under the
> project venv — the same command works on macOS, Linux, and Windows.
