#!/usr/bin/env python3
"""Normalize a Jira story file into the canonical format used by the
create-diagram / update-diagram prompts.

Two modes
---------

**Create mode** (default — no `--diagram` supplied):
    Rewrites a raw business note into a build-from-scratch canonical
    story (the shape of `template/surgical-story-template.txt`). The output names
    components, their connections, and the GCP services involved, but
    does NOT pretend to know any existing diagram state.

**Update mode** (`--diagram <path>` supplied):
    Loads the target diagram, generates a label-only summary of every
    node and edge, and rewrites the raw business note into a *surgical
    diff* story (the shape of `jira-stories/PROJ-124.txt`). Section 3
    will quote exact existing node/edge labels verbatim with explicit
    REMOVE / ADD lists; section 7 contains an ASCII Before → After flow
    using those labels; section 10 acceptance criteria are written so
    each one can be verified against `read_diagram_summary` output.

Output
------
The script NEVER modifies the input file. It writes a sibling file
`<KEY>-surgical.txt` next to the input (e.g. `PROJ-124.txt` →
`PROJ-124-surgical.txt`), and the diagram prompts read THAT file via
`read_story` instead of the raw input. Override the destination with
`--output <path>`.

Decision tree (DEFAULT IS ALWAYS-FRESH — every invocation regenerates)
-----------------------------------------------------------------------
- CREATE mode, input canonical → COPY input verbatim into surgical
  (no LLM call needed — there is no diagram context to weave in).
  Reported as `REFRESHED (copy)`.
- CREATE mode, input raw → LLM rewrite into surgical. Reported as
  `REFRESHED (LLM)`.
- UPDATE mode (any input) → ALWAYS LLM rewrite, because the surgical
  must quote the current diagram's labels verbatim and only the LLM
  rewrite path knows how to do that. Reported as `REFRESHED (LLM)`.
- `--skip-if-fresh` is the EXPLICIT opt-out: if the surgical already
  exists, is canonical, and the source isn't newer (mtime), skip the
  rewrite. Reported as `FORMAT_OK`.
- LLM rewrite needed but no `ANTHROPIC_API_KEY` / SDK installed →
  emit `NEEDS_NORMALIZATION` JSON payload with `target_path` pointing
  to the surgical file. Exit 2. The calling LLM (Copilot / Claude
  Code in the conversation) writes to `target_path` itself.

Why always-fresh?
- The user's mental model is: "if I'm running the diagram prompt, the
  surgical text must reflect what's on disk RIGHT NOW." The old
  skip-if-canonical fast path silently leaked stale text through the
  pipeline whenever the user edited the source without changing its
  structural validity.
- For CREATE flows the cost is zero (COPY path).
- For UPDATE flows the cost is one LLM call per invocation, which is
  desirable: diagrams change between runs, and the surgical must
  re-quote the current labels.
- `--skip-if-fresh` is provided for power-users doing rapid local
  iteration who want to avoid the LLM cost when nothing has changed.

Invocation
----------
    # Create-flow: no diagram context.
    python scripts/normalize_jira_story.py jira-stories/PROJ-125.txt

    # Update-flow: pass the target diagram so the rewrite is surgical.
    python scripts/normalize_jira_story.py jira-stories/PROJ-124.txt \\
        --diagram PROJ-123-20260524-045255.drawio

    # Inspection / CI:
    python scripts/normalize_jira_story.py jira-stories/PROJ-124.txt --check
    python scripts/normalize_jira_story.py jira-stories/PROJ-124.txt --dry-run

Exit codes
----------
  0   File is canonical (already, or after a successful rewrite).
  1   Hard error (file not found, malformed args, ...).
  2   File needs normalization but it could not be done automatically
      (Anthropic SDK / API key missing, or `--check` reported the
      file as non-canonical).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
# Reference template that defines the canonical surgical-text shape. The LLM
# rewrite path is shown this file as the structure to match; `PROJ-123.txt`
# remains a worked example story but is no longer the template.
DEFAULT_TEMPLATE = REPO_ROOT / "template" / "surgical-story-template.txt"
DEFAULT_DIAGRAMS_DIR = REPO_ROOT / "diagrams"
MCP_SRC = REPO_ROOT / "drawio-mcp-server" / "src"
if MCP_SRC.exists() and str(MCP_SRC) not in sys.path:
    sys.path.insert(0, str(MCP_SRC))


def _maybe_reexec_under_venv() -> None:
    """Auto-promote to the project venv's Python if we aren't already
    running under it.

    Why: the user types the same command on every OS —

        python scripts/normalize_jira_story.py jira-stories/PROJ-124.txt

    — but the venv Python lives at different paths per OS
    (`.venv/bin/python` on macOS/Linux, `.venv\\Scripts\\python.exe` on
    Windows) and is the only interpreter that's guaranteed to have
    `anthropic` and the `drawio_mcp_server` modules installed. This
    function detects the host OS via `sys.platform`, locates the
    matching venv Python, and re-execs the script under it. If the
    venv is missing (setup not run yet) we silently continue under the
    invoking Python — the user will get a clear ImportError later if
    they try the LLM-rewrite path without `anthropic` installed.

    Loop guard: the `_NORMALIZER_VENV_BOOTSTRAPPED` env var is set
    before exec so a misconfigured venv can't trigger infinite
    re-execs.
    """
    if os.environ.get("_NORMALIZER_VENV_BOOTSTRAPPED"):
        return

    if sys.platform == "win32":
        venv_python = (
            REPO_ROOT / "drawio-mcp-server" / ".venv" / "Scripts" / "python.exe"
        )
    else:
        venv_python = REPO_ROOT / "drawio-mcp-server" / ".venv" / "bin" / "python"

    if not venv_python.exists():
        return  # no venv yet — run with whatever Python invoked us

    try:
        already_in_venv = (
            Path(sys.executable).resolve() == venv_python.resolve()
        )
    except (OSError, RuntimeError):
        already_in_venv = False
    if already_in_venv:
        return

    new_env = dict(os.environ)
    new_env["_NORMALIZER_VENV_BOOTSTRAPPED"] = "1"
    argv = [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]]

    if sys.platform == "win32":
        # Windows: os.execv replaces the process image but the parent
        # shell's exit code handling is unreliable. Use subprocess +
        # sys.exit to mirror exec semantics cleanly.
        import subprocess

        completed = subprocess.run(argv, env=new_env)
        sys.exit(completed.returncode)
    else:
        os.execve(str(venv_python), argv, new_env)


_maybe_reexec_under_venv()

REQUIRED_HEADERS = ("Key:", "Title:")
REQUIRED_SECTIONS = (
    r"^\s*1\.\s*Background\b",
    r"^\s*2\.\s*Objective\b",
    r"^\s*3\.\s*In Scope\b",
    r"^\s*10\.\s*Acceptance Criteria\b",
)

MODEL_DEFAULT = "claude-sonnet-4-6"

SYSTEM_PROMPT_COMMON = """You rewrite raw Jira-style business notes into a strict
canonical story format used by an architecture-diagram automation pipeline
(MCP server with tools add_node / add_edge / update_node / remove_element /
read_diagram_summary).

GENERAL RULES
- Output ONLY the rewritten story text. No preamble, no code fences, no
  trailing commentary.
- The output must follow the structure of the reference template
  verbatim: same `Key:` / `Type:` / `Title:` headers, same numbered
  sections 1..11 in the same order, same wording for section names.
- `Key:` must match the filename's Jira key (e.g. `PROJ-125` for
  `PROJ-125.txt`). `Type:` defaults to `Story` unless the raw note
  says otherwise. `Title:` is a one-line summary derived from the
  raw note's intent.
- When the raw note references GCP services by name (BigQuery, Cloud
  Composer, Pub/Sub, Cloud Run, GCS, Cloud SQL, Document AI, etc.),
  name each one explicitly in section 3 and section 10 so the
  downstream prompt can map them to the official GCP icons via
  `gcp_icon=...`.

REAL-WORLD INPUT SHAPE (what business notes actually look like)
The business will typically hand you a thin file with ONLY sections 1,
2, 3, 4 — and even those may be partially leftover from a different
story (a copy-paste of the template). The ONLY part you can trust to
reflect the actual intent is section 3 (In Scope), which contains
free-form prose like "file comes from onprem to gcs bucket / composer
batch job loads to bigquery staging / staging transforms to curation".
Handle this as follows:

- TREAT THE HEADER AS UNTRUSTED. If `Key:`, `Title:`, or `Type:` in
  the input don't fit what section 3 actually describes (common when
  the user cloned `PROJ-123.txt` as their starting template),
  OVERRIDE them silently. `Key:` ALWAYS comes from the filename;
  `Title:` ALWAYS summarizes the real subject in section 3.
- TREAT SECTIONS 1 & 2 (Background / Objective) AS UNTRUSTED. If they
  describe a different subject from section 3 (e.g. they talk about
  "document AI" but section 3 is about "data ingestion onprem to
  GCP"), REWRITE them to describe the section 3 subject. Preserve
  language style of the reference template, not of the stale input.
- TREAT SECTION 3 AS THE TRUTH. Extract every concrete artifact named
  in its prose: components (GCS bucket, Composer, BigQuery staging,
  BigQuery curation, Pub/Sub, etc.), connections ("file comes to
  GCS", "Composer loads to staging"), behaviours (sensor every 5
  minutes, event on arrival). These drive sections 5–11.
- SYNTHESIZE SECTIONS 5–11. They will be missing from the input.
  Generate plausible content grounded in section 3:
    5. Functional Requirements (one FR per discrete capability in §3)
    6. Non-Functional Requirements (boilerplate is fine — perf,
       reliability, security, observability, cost; use `{placeholder}`
       for numbers you don't have)
    7. Proposed Architecture (an ASCII flow line in CREATE mode; a
       Before/After delta in UPDATE mode — see the per-mode rules below)
    8. Dependencies (project provisioning, IAM, etc.)
    9. Assumptions (what you took as given when filling sections 5–8)
   10. Acceptance Criteria (each component and connection in §3
       must be checkable here, written so the downstream
       `read_diagram_summary` verifier can tick them off)
   11. Risks (real risks the §3 architecture invites: data quality,
       cost overrun, schedule, quota, drift)
- Do NOT invent stakeholders, deadlines, vendor names, or specific
  numeric thresholds that aren't implied by section 3. Use the
  `{placeholder}` convention for those.
"""

SYSTEM_PROMPT_CREATE = SYSTEM_PROMPT_COMMON + """
MODE: CREATE (no existing diagram — build-from-scratch story).

- In section 3 (In Scope), list each component the new system needs,
  and for every GCP component include its exact GCP service name in
  parentheses so the downstream `add_node` call can set
  `gcp_icon="<service>"`. List connections at the end of section 3 as
  bullet lines `Source → Target : <≤3-word edge label>`.
- Section 7 (Proposed Architecture) MUST end with a single ASCII flow
  line using the component labels you introduced in section 3.
- Section 10 (Acceptance Criteria) MUST list each new component and
  each new edge as a separately verifiable bullet so the downstream
  diagram review can tick them off against `read_diagram_summary`.
"""

SYSTEM_PROMPT_UPDATE = SYSTEM_PROMPT_COMMON + """
MODE: UPDATE (an existing diagram is supplied — surgical-diff story).

You will receive the current diagram's `read_diagram_summary` output as
JSON. Treat node labels and edge `from`/`to`/`relation` strings in that
summary as CANONICAL — they are the exact strings the downstream
`remove_element` / `add_edge` calls must use.

The input business note will almost always be FREE-FORM PROSE in
section 3 (e.g. "split staging and curation into two stages",
"composer sensor checks every 5 min"), NOT an explicit REMOVE/ADD
list. YOU must compute the REMOVE/ADD lists yourself by:
  1. Reading the prose intent in section 3 (and only section 3 — sections
     1, 2 are likely stale boilerplate).
  2. Comparing it to the supplied diagram summary.
  3. Deciding for every node that the prose touches: keep, rename
     (`update_node`), split (`remove_element` + multiple `add_node`),
     or new (`add_node`).
  4. For every edge whose endpoint is being removed/renamed, decide:
     reroute or delete. No dangling edges.
The REMOVE/ADD lists you produce in section 3 of the OUTPUT must
quote labels verbatim from the diagram summary (for removes) and from
your new additions (for adds).

Section 3 (In Scope) MUST be structured as four sub-blocks in this
exact order, quoting labels verbatim from the supplied diagram summary:

  Nodes to REMOVE (quote labels verbatim — `remove_element` by id):
    - `"<existing label>"`  (current id likely `<nodeId>`)

  Nodes to ADD (use `add_node` with the official GCP icon — `gcp_icon`
  is MANDATORY for every GCP service):
    - Label: `"<new label>"`   `gcp_icon="<service>"`

  Edges to REMOVE (quote source/target labels verbatim — `remove_element`
  by id):
    - `<src label> → <tgt label>` : `"<edge label>"`   (current id likely `<edgeId>`)

  Edges to ADD (use `add_edge` — keep labels ≤ 3 words / ~24 chars):
    - `<src label>` → `<tgt label>`   label: `"<edge label>"`

After the four sub-blocks, append a single PRESERVE clause naming every
other node and edge in the supplied summary that MUST be kept unchanged.

Section 7 (Proposed Architecture — Diagram Delta — EXPLICIT) MUST
contain two ASCII flow blocks using verbatim labels:

  BEFORE (current diagram, exact labels):
    <flow lines using existing labels>

  AFTER (target diagram, exact labels):
    <flow lines using new labels>

Coverage rule for edges: when you REMOVE a node, you MUST account for
every existing edge in the supplied summary whose `from` OR `to` matches
that node's label. For each such edge, decide: keep it (impossible if
endpoint deleted — must reroute), reroute it (add to "Edges to ADD" with
the new target), or delete it (add to "Edges to REMOVE"). Do NOT leave
dangling edges.

Section 10 (Acceptance Criteria — verifiable against
`read_diagram_summary`) MUST contain at minimum:
  AC1: `read_diagram_summary` returns NO node whose label is <each removed label>.
  AC2: `read_diagram_summary` returns exactly these N new node labels: <list>.
  AC3: Each new GCP node uses its official GCP icon (named explicitly).
  AC4: The new edge sequence A→B→C→... exists end-to-end in the summary.
  AC5: Every rerouted edge from the diff is present with the new target.
  AC6: Total node count = (previous − removed + added); edge count
       reflects the net delta. Every node/edge NOT listed in section 3
       is preserved verbatim.
  AC7: Updated diagram is saved as a NEW timestamped file under `diagrams/`
       (do not overwrite the baseline).

Section 11 (Risks) MUST include an "LLM no-op risk" bullet if any
removed-node label contains words from the new labels (e.g. removing a
node literally labelled `"BigQuery (staging & curation)"` while adding
"BigQuery — Staging Layer" and "BigQuery — Curation Layer" — the
substring match can fool a casual reader into thinking the split
already exists). Mitigation: explicit remove_element + add_node calls,
not a relabel.
"""

USER_PROMPT_CREATE = """REFERENCE TEMPLATE (canonical format — match its structure exactly):
---
{template}
---

JIRA KEY (derived from filename): {jira_key}

RAW BUSINESS NOTE (rewrite this into canonical CREATE-mode format):
---
{raw}
---

Rewrite the raw note now. Output the rewritten story text only.
"""

USER_PROMPT_UPDATE = """REFERENCE TEMPLATE (canonical format — match its structure exactly):
---
{template}
---

CURRENT DIAGRAM SUMMARY (this is what `read_diagram_summary` returns for
the target diagram — node labels and edge from/to/relation strings here
are CANONICAL; quote them verbatim in section 3 and section 7):
---
{diagram_summary}
---

JIRA KEY (derived from filename): {jira_key}

RAW BUSINESS NOTE (rewrite this into canonical UPDATE-mode surgical-diff format):
---
{raw}
---

Rewrite the raw note now. Output the rewritten story text only.
"""


def is_canonical(text: str, *, filename_key: str | None = None) -> tuple[bool, list[str]]:
    """Return (ok, missing). `missing` lists which checks failed.

    Structural checks: the file must have `Key:` + `Title:` headers and
    sections 1, 2, 3, 10. Optional `filename_key` adds a semantic
    check: when the file is named `PROJ-125.txt`, its `Key:` line must
    read `PROJ-125`. This catches a common copy-paste mistake where a
    business author cloned an older story file and forgot to update
    the key — without this check, the stale key would silently flow
    through every downstream step.
    """
    missing: list[str] = []
    for header in REQUIRED_HEADERS:
        if not re.search(rf"^{re.escape(header)}\s", text, re.MULTILINE):
            missing.append(f"missing header: {header}")
    for pattern in REQUIRED_SECTIONS:
        if not re.search(pattern, text, re.MULTILINE):
            missing.append(f"missing section: {pattern}")
    if filename_key:
        m = re.search(r"^Key:\s*(\S+)", text, re.MULTILINE)
        if m and m.group(1).strip() != filename_key:
            missing.append(
                f"key mismatch: filename says {filename_key!r} but `Key:` "
                f"line says {m.group(1)!r} (stale copy-paste from another story?)"
            )
    return (not missing), missing


def derive_jira_key(path: Path) -> str:
    """`PROJ-124.txt` -> `PROJ-124`."""
    return path.stem


def load_template(template_path: Path) -> str:
    if not template_path.exists():
        raise FileNotFoundError(
            f"Reference template not found: {template_path}. "
            f"Pass --template to point at a different one."
        )
    return template_path.read_text(encoding="utf-8")


def load_diagram_summary(diagram_arg: str, diagrams_dir: Path) -> str:
    """Resolve `diagram_arg` against `diagrams_dir` (or treat as an
    absolute/relative path) and return the JSON-serialized summary."""
    try:
        from drawio_mcp_server.drawio.summarize import summarize
        from drawio_mcp_server.util.diagram_store import DiagramStore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Could not import drawio_mcp_server modules from "
            f"{MCP_SRC}. Make sure the repo layout is intact."
        ) from exc

    candidate = Path(diagram_arg)
    if candidate.is_absolute() and candidate.exists():
        root = candidate.parent
        name = candidate.name
    else:
        root = diagrams_dir.resolve()
        name = candidate.name if candidate.parent == Path(".") else str(candidate)

    store = DiagramStore(root)
    if not store.exists(name):
        raise FileNotFoundError(
            f"Diagram not found: {name} (looked under {root})"
        )
    diagram = store.load(name)
    summary = summarize(diagram).model_dump(by_alias=True)
    summary["resolved_path"] = str((root / (name if name.endswith(".drawio") else name + ".drawio")).resolve())
    return json.dumps(summary, indent=2)


def rewrite_with_anthropic(
    *,
    raw: str,
    template: str,
    jira_key: str,
    model: str,
    diagram_summary: str | None,
) -> str:
    """Call Claude to rewrite. Prompt caching on the system prompt +
    reference template (both stable across runs) keeps repeat calls
    cheap."""
    try:
        from anthropic import Anthropic
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "anthropic SDK not installed. Install with "
            "`pip install anthropic` or run with --check / fallback mode."
        ) from exc

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Export it or run with --check / "
            "fallback mode."
        )

    if diagram_summary is None:
        system_text = SYSTEM_PROMPT_CREATE
        user_text = USER_PROMPT_CREATE.format(
            template=template, jira_key=jira_key, raw=raw
        )
    else:
        system_text = SYSTEM_PROMPT_UPDATE
        user_text = USER_PROMPT_UPDATE.format(
            template=template,
            diagram_summary=diagram_summary,
            jira_key=jira_key,
            raw=raw,
        )

    client = Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_text,
                    }
                ],
            }
        ],
    )

    parts: list[str] = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    rewritten = "".join(parts).strip()
    if not rewritten:
        raise RuntimeError("Empty response from Anthropic API.")
    return rewritten + "\n"


def emit_delegate_payload(
    *,
    story_path: Path,
    target_path: Path,
    raw: str,
    template: str,
    jira_key: str,
    missing: Iterable[str],
    reason: str,
    diagram_summary: str | None,
) -> None:
    """Print a structured payload the calling LLM can act on, then exit 2."""
    mode = "update" if diagram_summary is not None else "create"
    payload = {
        "status": "NEEDS_NORMALIZATION",
        "mode": mode,
        "source_story_path": str(story_path),
        "target_path": str(target_path),
        "jira_key": jira_key,
        "missing_checks": list(missing),
        "reason": reason,
        "instructions_for_calling_llm": (
            f"This Jira file is not in the canonical format the diagram "
            f"prompts expect. Do NOT modify the source file "
            f"`{story_path.name}` — instead, use Write to CREATE a new "
            f"file at `{target_path}` containing a canonical-format "
            f"story (Key:, Type:, Title:, then numbered sections 1..11). "
            + (
                "Because a diagram summary is supplied, produce a "
                "surgical-diff story in the shape of PROJ-124.txt: "
                "quote existing node and edge labels VERBATIM from "
                "the supplied `current_diagram_summary` field, then "
                "structure section 3 as four sub-blocks (Nodes to "
                "REMOVE / Nodes to ADD / Edges to REMOVE / Edges to "
                "ADD) and section 7 as ASCII Before/After flows. "
                "Cover every edge whose endpoint is being removed "
                "(reroute or delete — no dangling edges). Make "
                "section 10 acceptance criteria verifiable against "
                "`read_diagram_summary`."
                if diagram_summary is not None
                else "Produce a build-from-scratch story in the shape "
                "of template/surgical-story-template.txt: list "
                "components and their connections in section 3, an "
                "ASCII flow in section 7, and per-component acceptance "
                "criteria in section 10."
            )
            + f" Preserve every fact in the raw note. Use {{placeholder}} "
            f"for unknown values. After writing `{target_path.name}`, "
            f"re-run normalize_jira_story.py with --check to confirm "
            f"canonical format. The downstream diagram prompts will "
            f"call read_story with name=\"{target_path.name}\" — NOT "
            f"the original `{story_path.name}` — so make sure the new "
            f"file is what gets created."
        ),
        "reference_template": template,
        "raw_story_text": raw,
    }
    if diagram_summary is not None:
        payload["current_diagram_summary"] = json.loads(diagram_summary)
    print(json.dumps(payload, indent=2))
    sys.exit(2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize a Jira story file into the canonical format "
            "consumed by the create-diagram / update-diagram prompts. "
            "Pass --diagram to switch to surgical-diff (update) mode."
        )
    )
    parser.add_argument("story", type=Path, help="Path to the Jira story file.")
    parser.add_argument(
        "--diagram",
        default=None,
        help=(
            "Target diagram filename (under --diagrams-dir) or absolute "
            "path. When supplied, the rewrite switches to surgical-diff "
            "(UPDATE) mode and embeds the diagram's read_diagram_summary "
            "into the LLM prompt so the output quotes existing labels "
            "verbatim. Omit for a CREATE-flow story."
        ),
    )
    parser.add_argument(
        "--diagrams-dir",
        type=Path,
        default=DEFAULT_DIAGRAMS_DIR,
        help=f"Diagrams root (default: {DEFAULT_DIAGRAMS_DIR}).",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=DEFAULT_TEMPLATE,
        help=(
            "Reference template (defaults to "
            "template/surgical-story-template.txt). "
            "Its structure is what every story is rewritten to match."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only report whether the file is canonical. Do not rewrite.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the rewritten content to stdout without modifying the file.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("NORMALIZER_MODEL", MODEL_DEFAULT),
        help=f"Anthropic model id (default: {MODEL_DEFAULT}).",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not write a .bak file before overwriting.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Accepted for back-compat. Always-fresh is now the default: "
            "every invocation regenerates the surgical from the source. "
            "Use --skip-if-fresh to opt out of this default."
        ),
    )
    parser.add_argument(
        "--skip-if-fresh",
        action="store_true",
        help=(
            "Opt out of the always-regenerate default. Skip the rewrite "
            "when the surgical file already exists, is canonical, and "
            "is at least as new as the source (mtime). Useful for "
            "rapid local iteration when you want to avoid LLM cost on "
            "repeat runs against unchanged inputs."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Override the surgical output path. Defaults to "
            "<input-dir>/<KEY>-surgical<ext> next to the input file."
        ),
    )
    args = parser.parse_args(argv)

    story_path: Path = args.story.resolve()
    if not story_path.exists():
        print(f"[normalizer] ERROR: story not found: {story_path}", file=sys.stderr)
        return 1

    target_path: Path = (
        args.output.resolve()
        if args.output is not None
        else story_path.parent / f"{story_path.stem}-surgical{story_path.suffix}"
    )

    jira_key = derive_jira_key(story_path)
    raw = story_path.read_text(encoding="utf-8")
    raw_ok, raw_missing = is_canonical(raw, filename_key=jira_key)
    mode = "update" if args.diagram else "create"

    surgical_exists = target_path.exists()
    surgical_ok = False
    if surgical_exists:
        surgical_text = target_path.read_text(encoding="utf-8")
        surgical_ok, _ = is_canonical(surgical_text, filename_key=jira_key)

    source_newer_than_surgical = False
    if surgical_exists:
        try:
            source_newer_than_surgical = (
                story_path.stat().st_mtime > target_path.stat().st_mtime
            )
        except OSError:
            source_newer_than_surgical = False

    # ALWAYS-FRESH IS THE DEFAULT.
    # Every prompt invocation (and every direct CLI run, unless the
    # user passes --skip-if-fresh) regenerates `<KEY>-surgical.txt`
    # from the current source — and, in UPDATE mode, from the current
    # diagram state. The user's mental model is "I'm running the
    # diagram prompt, so the surgical text must reflect what's on
    # disk RIGHT NOW". The old fast-path-skip violated that.
    #
    # `--skip-if-fresh` is the explicit opt-out for the "I know
    # nothing's changed, don't burn LLM cost on a redundant run" case.
    skip_allowed = args.skip_if_fresh and not args.force
    skip_fresh = (
        skip_allowed
        and surgical_ok
        and not source_newer_than_surgical
    )

    if args.check:
        if surgical_ok and not source_newer_than_surgical:
            print(
                f"[normalizer] FORMAT_OK: {target_path.name} exists and is canonical."
            )
            return 0
        why = []
        if not surgical_exists:
            why.append("surgical absent")
        elif not surgical_ok:
            why.append("surgical not canonical")
        if source_newer_than_surgical:
            why.append("source newer than surgical")
        print(
            f"[normalizer] NEEDS_NORMALIZATION: {target_path.name} "
            f"({', '.join(why)}, mode={mode})"
            + ("\n" + "\n".join(f"  - {m}" for m in raw_missing) if not raw_ok else "")
        )
        return 2

    # Explicit opt-out path: user asked to skip when nothing's changed.
    if skip_fresh:
        print(
            f"[normalizer] FORMAT_OK: {target_path.name} already exists and is "
            f"canonical, source not newer (mode={mode}, --skip-if-fresh "
            f"honored — omit that flag to force a fresh rewrite)."
        )
        return 0

    # CREATE-mode short circuit: if the input is structurally canonical
    # AND we're in CREATE mode (no diagram context to incorporate),
    # mirroring the source verbatim is correct and avoids an LLM call.
    # In UPDATE mode we never short-circuit — the surgical must
    # incorporate the current diagram's labels, which only the LLM
    # rewrite path computes.
    if raw_ok and mode == "create":
        _maybe_backup(target_path, args.no_backup)
        target_path.write_text(raw, encoding="utf-8")
        print(
            f"[normalizer] REFRESHED (copy): {story_path.name} → "
            f"{target_path.name} (input canonical, CREATE mode — "
            f"surgical mirrors source verbatim, no LLM call needed)."
        )
        return 0

    if not raw.strip():
        print(
            f"[normalizer] ERROR: {story_path.name} is empty. Add the raw "
            f"business note first.",
            file=sys.stderr,
        )
        return 1

    try:
        template = load_template(args.template.resolve())
    except FileNotFoundError as exc:
        print(f"[normalizer] ERROR: {exc}", file=sys.stderr)
        return 1

    diagram_summary: str | None = None
    if args.diagram:
        try:
            diagram_summary = load_diagram_summary(args.diagram, args.diagrams_dir)
        except (FileNotFoundError, RuntimeError) as exc:
            print(f"[normalizer] ERROR: {exc}", file=sys.stderr)
            return 1

    try:
        rewritten = rewrite_with_anthropic(
            raw=raw,
            template=template,
            jira_key=jira_key,
            model=args.model,
            diagram_summary=diagram_summary,
        )
    except RuntimeError as exc:
        emit_delegate_payload(
            story_path=story_path,
            target_path=target_path,
            raw=raw,
            template=template,
            jira_key=jira_key,
            missing=raw_missing or ["force-rerun requested"],
            reason=str(exc),
            diagram_summary=diagram_summary,
        )
        return 2  # unreachable — emit_delegate_payload calls sys.exit(2)

    if args.dry_run:
        sys.stdout.write(rewritten)
        return 0

    _maybe_backup(target_path, args.no_backup)
    target_path.write_text(rewritten, encoding="utf-8")
    print(
        f"[normalizer] REFRESHED (LLM): wrote {target_path.name} in "
        f"canonical {mode}-mode format ({len(rewritten)} chars). "
        f"Source {story_path.name} left untouched."
    )
    return 0


def _maybe_backup(target_path: Path, skip: bool) -> None:
    """If `target_path` already exists, copy it to `<target>.bak` before
    the caller overwrites — skipped when `skip` is True."""
    if skip or not target_path.exists():
        return
    backup_path = target_path.with_suffix(target_path.suffix + ".bak")
    backup_path.write_text(target_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[normalizer] wrote backup: {backup_path.name}")


if __name__ == "__main__":
    raise SystemExit(main())
