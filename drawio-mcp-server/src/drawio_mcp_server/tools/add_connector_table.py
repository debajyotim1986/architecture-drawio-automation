"""Embed the per-connector details table directly inside a diagram,
positioned below the swimlanes.

Layout — ONE wide table with each detail category as its own column.

    ┌─────┬─────────┬─────────┬────────┬─────────────┬──────────┬────────┬──────┬─────────┬─────────────┬─────────────┬───────────────┬────────────┬──────────────┐
    │Step │Source   │Target   │Action  │Interaction  │Protocol  │AuthN/Z │Data  │Network  │Performance  │Reliability  │Observability  │Compliance  │Dependencies  │
    │     │         │         │        │Pattern      │& API     │        │      │& Conn.  │& SLA        │& Resilience │               │& Gov.      │& Failure     │
    ├─────┼─────────┼─────────┼────────┼─────────────┼──────────┼────────┼──────┼─────────┼─────────────┼─────────────┼───────────────┼────────────┼──────────────┤
    │ 1   │On-Prem  │GCS      │uploads │{TBD}        │{TBD}     │{TBD}   │{TBD} │{TBD}    │{TBD}        │{TBD}        │{TBD}          │{TBD}       │{TBD}         │
    │ 2   │GCS      │Pub/Sub  │event   │{TBD}        │{TBD}     │{TBD}   │{TBD} │{TBD}    │{TBD}        │{TBD}        │{TBD}          │{TBD}       │{TBD}         │
    │ … │
    └─────┴─────────┴─────────┴────────┴─────────────┴──────────┴────────┴──────┴─────────┴─────────────┴─────────────┴───────────────┴────────────┴──────────────┘

14 columns total. Each numbered edge gets ONE row across all
columns. Sourced from `jira-stories/<KEY>-connectors.md` — when that
file has real values they show in the cells; cells still marked
`{TBD}` in the .md render with muted styling so reviewers can scan
for what's missing.

The table sits BELOW the bottom edge of the lowest swimlane with a
60 px gap. Title bar at top reads "Connector Details — <KEY>".

Idempotent: cells use the `ctbl_` id prefix and are removed before
each re-layout, so refreshing the table after editing the .md
updates the diagram in place.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from mcp.types import Tool

from ..types import DiagramNode
from ..util.config import ServerConfig
from ..util.diagram_store import DiagramStore

# Layout — single wide table, 14 columns, 1 row per numbered edge.
_TABLE_GAP_BELOW_SWIMLANES = 60.0
_TITLE_HEIGHT = 50.0
_HEADER_HEIGHT = 64.0    # taller to fit two-word column names without overflow
_DATA_ROW_HEIGHT = 90.0  # multi-line values like a sentence-long Auth spec

# Column widths — in left-to-right order. The 4 metadata columns
# (Step, Source, Target, Action) come first, then the 10 detail
# categories from the connector-details schema. Total width ~2200 px
# — wider than the 6-swimlane layout, but the values themselves
# need room to be readable.
_COLUMNS: tuple[tuple[str, float], ...] = (
    ("Step", 50.0),
    ("Source", 150.0),
    ("Target", 150.0),
    ("Action", 110.0),
    ("Interaction Pattern", 160.0),
    ("Protocol & API", 200.0),
    ("AuthN & AuthZ", 180.0),
    ("Data", 180.0),
    ("Network & Connectivity", 200.0),
    ("Performance & SLA", 180.0),
    ("Reliability & Resilience", 180.0),
    ("Observability", 160.0),
    ("Compliance & Governance", 180.0),
    ("Dependencies & Failure Mode", 200.0),
)

# Cell styles
_TITLE_STYLE = (
    "text;html=1;align=center;verticalAlign=middle;fontSize=18;fontStyle=1;"
    "fillColor=#1e6091;fontColor=#ffffff;strokeColor=#1e6091;whiteSpace=wrap;"
)
_HEADER_CELL_STYLE = (
    "text;html=1;align=center;verticalAlign=middle;fontSize=11;fontStyle=1;"
    "fillColor=#dae8fc;strokeColor=#6c8ebf;fontColor=#1e3a5f;whiteSpace=wrap;"
    "spacingLeft=4;spacingRight=4;"
)
_STEP_CELL_STYLE = (
    "text;html=1;align=center;verticalAlign=middle;fontSize=14;fontStyle=1;"
    "fontColor=#1e6091;fillColor=#ffffff;strokeColor=#999999;whiteSpace=wrap;"
)
_META_CELL_STYLE = (
    # Source / Target / Action columns — slightly emphasized so the
    # connector identity stands out from the detail values.
    "text;html=1;align=left;verticalAlign=middle;fontSize=11;fontStyle=1;"
    "fontColor=#1e3a5f;fillColor=#ffffff;strokeColor=#999999;"
    "whiteSpace=wrap;spacingLeft=8;spacingRight=8;"
)
_DATA_CELL_STYLE = (
    "text;html=1;align=left;verticalAlign=top;fontSize=10;whiteSpace=wrap;"
    "fillColor=#ffffff;strokeColor=#999999;spacingTop=6;spacingLeft=6;"
    "spacingRight=6;"
)
_DATA_CELL_STYLE_TBD = (
    # Muted styling so reviewers can scan for {TBD}-only columns at a
    # glance and prioritize where to fill in real values.
    "text;html=1;align=center;verticalAlign=middle;fontSize=10;fontStyle=2;"
    "fontColor=#888888;fillColor=#fafafa;strokeColor=#cccccc;whiteSpace=wrap;"
)

_ID_PREFIX = "ctbl_"

# `{TBD}` of ANY form (plain `{TBD}` OR qualified `{TBD: <hint>}`) is
# banned in the embedded table. The Always-Fill rule says every cell
# must carry a concrete value — mark assumptions with `(assumed)` or
# `(default)` rather than leaving a `{TBD}`. The pre-flight guard
# below fails the embed if ANY `{TBD` token is found in the .md.
_MAX_ANY_TBD = 0

# Override via env var when you genuinely want to embed a half-filled
# table (e.g. mid-iteration). Default is zero-tolerance.
_OVERRIDE_ENV = "ADD_CONNECTOR_TABLE_ALLOW_TBD"


add_connector_table_tool = Tool(
    name="add_connector_table",
    description=(
        "Embed the per-connector details table BELOW the swimlanes of a "
        "diagram. One row per numbered edge (sorted by step_index), with "
        "columns Step / Source / Target / Action / Details. The Details "
        "cell concatenates the 10 connector-details category fields "
        "(Interaction Pattern, Protocol & API, AuthN/Z, Data, Network, "
        "Performance, Reliability, Observability, Compliance, "
        "Dependencies). When `connectors_md` points at a populated "
        "<KEY>-connectors.md the fields are pulled from there; when "
        "missing the cell shows {TBD}. Call this AFTER "
        "generate_connector_details.py in the create-diagram flow so "
        "the .md is on disk when the embed runs. Idempotent — removes "
        "any previously-embedded table cells before laying down a "
        "fresh one."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "diagram": {"type": "string", "description": "Diagram filename."},
            "connectors_md": {
                "type": "string",
                "description": (
                    "Optional path (relative to repo root, or absolute) "
                    "to the <KEY>-connectors.md file. When omitted, the "
                    "tool tries `jira-stories/<KEY>-connectors.md` next "
                    "to the diagram's Jira key."
                ),
            },
            "title": {
                "type": "string",
                "description": (
                    "Override the title bar text. Defaults to "
                    "'Connector Details — <KEY>'."
                ),
            },
        },
        "required": ["diagram"],
        "additionalProperties": False,
    },
)


async def add_connector_table(args: dict[str, Any], cfg: ServerConfig) -> dict[str, Any]:
    diagram_name = str(args.get("diagram") or "")
    if not diagram_name:
        raise ValueError("`diagram` is required.")

    store = DiagramStore(cfg.diagrams_dir)
    diagram = store.load(diagram_name)

    # Drop any previously-embedded table cells so re-runs are idempotent.
    diagram.nodes = [n for n in diagram.nodes if not n.id.startswith(_ID_PREFIX)]

    # Get edges sorted by step number.
    edges = sorted(
        [e for e in diagram.edges if e.step_index is not None and e.step_index > 0],
        key=lambda e: e.step_index,  # type: ignore[arg-type]
    )
    if not edges:
        raise ValueError(
            "Diagram has no numbered edges; nothing to put in a table. "
            "Add edges first with add_edge."
        )

    # Compute anchor: leftmost swimlane x + bottom of lowest swimlane.
    swimlanes = [n for n in diagram.nodes if n.shape == "swimlane"]
    if swimlanes:
        anchor_x = min(n.x for n in swimlanes)
        anchor_y = max(n.y + n.height for n in swimlanes) + _TABLE_GAP_BELOW_SWIMLANES
    else:
        anchor_x = 40.0
        anchor_y = 100.0

    # Resolve Jira key from filename (e.g. PROJ-127-20260525-194821 → PROJ-127).
    jira_key = _resolve_jira_key(diagram_name)

    # Pull row data from connectors.md if available.
    md_rows: dict[int, dict[str, str]] = {}
    md_path = _resolve_md_path(args.get("connectors_md"), jira_key, cfg)
    if md_path is not None and md_path.exists():
        md_rows = _parse_connectors_md(md_path)

        # Pre-flight guard: refuse to embed a half-filled table.
        # ZERO `{TBD` of any form is allowed in the deliverable — the
        # Always-Fill rule says every cell must carry a concrete value
        # (mark assumptions with `(assumed)` or `(default)` rather
        # than `{TBD}`). Counts BOTH plain `{TBD}` AND qualified
        # `{TBD: <hint>}` because both forms render as visible
        # placeholders in the diagram.
        import os as _os
        import re as _re

        if _os.environ.get(_OVERRIDE_ENV) != "1":
            md_text = md_path.read_text(encoding="utf-8")
            tbd_total = len(_re.findall(r"\{TBD", md_text))
            if tbd_total > _MAX_ANY_TBD:
                raise ValueError(
                    f"{md_path.name} has {tbd_total} `{{TBD…}}` cells "
                    f"(max allowed: {_MAX_ANY_TBD}, i.e. NONE). The "
                    f"Always-Fill rule requires every cell to carry a "
                    f"concrete value — even fields that need business "
                    f"input must use a sensible default labelled "
                    f"`(assumed)` or `(default)`, NOT `{{TBD}}`.\n\n"
                    f"FIX: Re-run "
                    f"`python scripts/generate_connector_details.py "
                    f"--diagram <FILE> --story <STORY>` with "
                    f"ANTHROPIC_API_KEY set so the script auto-fills "
                    f"the table via Claude (the LLM is instructed to "
                    f"never use `{{TBD}}`). If you have no API key, the "
                    f"script exits 2 with a NEEDS_FILL payload — the "
                    f"calling LLM (Copilot Chat / Claude Code) must "
                    f"then edit `{md_path.name}` to replace every "
                    f"`{{TBD}}` with a concrete value per the "
                    f"Always-Fill directive in "
                    f".github/copilot-instructions.md.\n\n"
                    f"OVERRIDE (only for mid-iteration debugging): "
                    f"set the env var {_OVERRIDE_ENV}=1 to bypass."
                )

    label_of = {n.id: n.label for n in diagram.nodes}

    # Total table width — sum of column widths.
    total_w = sum(w for _, w in _COLUMNS)

    # Title bar (full table width)
    title_text = str(args.get("title") or f"Connector Details — {jira_key}")
    diagram.nodes.append(
        DiagramNode(
            id=f"{_ID_PREFIX}title",
            label=title_text,
            shape="rectangle",
            x=anchor_x,
            y=anchor_y,
            width=total_w,
            height=_TITLE_HEIGHT,
            raw_style=_TITLE_STYLE,
        )
    )
    y_cursor = anchor_y + _TITLE_HEIGHT

    # Header row — one cell per column.
    x_cursor = anchor_x
    for col_idx, (col_name, col_w) in enumerate(_COLUMNS):
        diagram.nodes.append(
            DiagramNode(
                id=f"{_ID_PREFIX}h{col_idx}",
                label=col_name.replace("&", "&amp;"),
                shape="rectangle",
                x=x_cursor,
                y=y_cursor,
                width=col_w,
                height=_HEADER_HEIGHT,
                raw_style=_HEADER_CELL_STYLE,
            )
        )
        x_cursor += col_w
    y_cursor += _HEADER_HEIGHT

    # Data rows — one ROW per numbered edge, one CELL per column.
    for edge in edges:
        step = int(edge.step_index)  # type: ignore[arg-type]
        src_label = label_of.get(edge.source_id, edge.source_id)
        tgt_label = label_of.get(edge.target_id, edge.target_id)
        action = edge.label or ""
        row_data = md_rows.get(step) or {}

        # Build values in column order. Step / Source / Target / Action
        # are computed from the diagram; the 10 detail columns come
        # from the connectors.md row (or {TBD}).
        row_values: list[tuple[str, bool]] = [
            (str(step), False),
            (src_label, False),
            (tgt_label, False),
            (action, False),
        ]
        for col_name, _ in _COLUMNS[4:]:  # the 10 detail columns
            raw_value = (row_data.get(col_name) or "{TBD}").strip() or "{TBD}"
            is_tbd = raw_value == "{TBD}"
            display = raw_value.replace("\\|", "|").replace("|", "&#124;")
            row_values.append((display, is_tbd))

        # Emit one cell per column for this row.
        x_cursor = anchor_x
        for col_idx, ((col_name, col_w), (value, is_tbd)) in enumerate(
            zip(_COLUMNS, row_values)
        ):
            if col_idx == 0:
                style = _STEP_CELL_STYLE
            elif col_idx < 4:
                style = _META_CELL_STYLE
            elif is_tbd:
                style = _DATA_CELL_STYLE_TBD
            else:
                style = _DATA_CELL_STYLE
            diagram.nodes.append(
                DiagramNode(
                    id=f"{_ID_PREFIX}r{step}_c{col_idx}",
                    label=value,
                    shape="rectangle",
                    x=x_cursor,
                    y=y_cursor,
                    width=col_w,
                    height=_DATA_ROW_HEIGHT,
                    raw_style=style,
                )
            )
            x_cursor += col_w
        y_cursor += _DATA_ROW_HEIGHT

    path = store.save(diagram_name, diagram)
    return {
        "diagram": diagram_name,
        "connectors": len(edges),
        "columns": len(_COLUMNS),
        "anchor_x": anchor_x,
        "anchor_y": anchor_y,
        "table_width": total_w,
        "md_source": str(md_path) if md_path else None,
        "path": path,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_jira_key(diagram_name: str) -> str:
    """`PROJ-127-20260525-194821.drawio` → `PROJ-127`."""
    stem = Path(diagram_name).stem
    m = re.match(r"^([A-Z]+-\d+)-\d{8}-\d{6}$", stem)
    return m.group(1) if m else stem


def _resolve_md_path(
    explicit: Any, jira_key: str, cfg: ServerConfig
) -> Path | None:
    """Decide where the connectors.md file lives. Order:
      1. explicit `connectors_md` arg (relative resolved against repo
         root inferred from cfg.diagrams_dir, or absolute)
      2. `<stories_dir>/<JIRA_KEY>-connectors.md`
    Returns None if no candidate exists.
    """
    if explicit:
        p = Path(str(explicit))
        if not p.is_absolute():
            # diagrams_dir is e.g. <repo>/diagrams → repo is parent
            repo_root = cfg.diagrams_dir.parent
            p = (repo_root / p).resolve()
        return p

    stories_dir = cfg.diagrams_dir.parent / "jira-stories"
    candidate = stories_dir / f"{jira_key}-connectors.md"
    return candidate if candidate.exists() else None


def _parse_connectors_md(path: Path) -> dict[int, dict[str, str]]:
    """Parse a connectors markdown table into {step_number: {col: value}}.

    Resilient to slight whitespace variation. Returns empty dict if the
    file isn't a markdown table or doesn't have a step column.
    """
    text = path.read_text(encoding="utf-8")

    # Find the header line that starts with '| Step |' and the separator
    # below it; everything from then on until a blank line is rows.
    header_line: str | None = None
    rows_lines: list[str] = []
    in_table = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not in_table:
            if line.lstrip().startswith("| Step "):
                header_line = line
                in_table = True
                continue
        else:
            stripped = line.strip()
            if not stripped or not stripped.startswith("|"):
                break
            # Skip the separator row "|---|---|..."
            if set(stripped.replace("|", "").replace("-", "").replace(":", "").strip()) == set():
                continue
            rows_lines.append(line)

    if not header_line:
        return {}

    headers = [h.strip() for h in _split_md_row(header_line)]
    out: dict[int, dict[str, str]] = {}
    for line in rows_lines:
        cells = [c.strip() for c in _split_md_row(line)]
        if len(cells) < len(headers):
            continue
        row_dict = dict(zip(headers, cells))
        step_raw = row_dict.get("Step", "")
        try:
            step = int(step_raw)
        except ValueError:
            continue
        out[step] = row_dict
    return out


def _split_md_row(line: str) -> list[str]:
    """Split a markdown table row at unescaped `|`. Trims the leading/
    trailing empty fields that come from `|...|` framing."""
    cells: list[str] = []
    cur = ""
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if ch == "|":
            cells.append(cur)
            cur = ""
            i += 1
            continue
        cur += ch
        i += 1
    cells.append(cur)
    # Drop leading/trailing framing cells (the `|...|` outer pipes).
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return cells


