#!/usr/bin/env bash
# Drop the bundled sample Jira story into jira-stories/DEMO-001.txt
# so you can immediately try the create-diagram flow. We deliberately
# use DEMO-001 (not PROJ-123) because jira-stories/PROJ-123.txt is the
# reference template the normalizer uses — overwriting it would break
# normalize_jira_story.py.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SRC="$REPO_ROOT/examples/sample-jira-story.txt"
DST="$REPO_ROOT/jira-stories/DEMO-001.txt"

[[ -f "$SRC" ]] || { echo "Missing $SRC — repo seems incomplete." >&2; exit 1; }
mkdir -p "$REPO_ROOT/jira-stories"

if [[ -f "$DST" ]] && ! cmp -s "$SRC" "$DST"; then
  echo "Refusing to overwrite an existing $DST that differs from the sample."
  echo "Delete it first if you want to reset:  rm \"$DST\""
  exit 1
fi

cp -f "$SRC" "$DST"
echo "Wrote $DST"
echo
echo "Now in VS Code Copilot Chat, paste:"
cat <<'PROMPT'

@workspace Use the prompt at prompts/create-diagram.md.
The story is jira-stories/DEMO-001.txt.
Save the diagram as diagrams/demo-001.drawio.

PROMPT
