#!/usr/bin/env python3
"""Cross-platform MCP server + diagram health check.

Use this as the last step of `create-diagram` / `update-diagram` flows
to confirm that:
  1. The MCP server's tool registry imports cleanly and advertises all
     13 expected tools (the same check the per-OS verify scripts do,
     ported to pure Python so a single invocation works on macOS,
     Linux, and Windows).
  2. (Optional, when `--diagram` is supplied) The just-finalized
     diagram is structurally sound: every edge endpoint resolves to a
     node, GCP-named labels are using their official icons, and there
     are no duplicate node labels.

Usage:
    python scripts/verify_mcp.py                            # server only
    python scripts/verify_mcp.py --diagram PROJ-XXX.drawio  # server + diagram
    python scripts/verify_mcp.py --diagram PROJ-XXX.drawio --strict

Self-bootstraps under the project venv (same mechanism as
scripts/normalize_jira_story.py) so the user types the same command on
every OS.

Exit codes:
    0  All checks passed.
    1  Hard error (venv missing → see message; file not found).
    2  Verification failed (missing tool, dangling edge, missing icon
       in --strict mode, etc.).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIAGRAMS_DIR = REPO_ROOT / "diagrams"
DEFAULT_ICONS_DIR = REPO_ROOT / "logo_icon_gcp"
MCP_SRC = REPO_ROOT / "drawio-mcp-server" / "src"
if MCP_SRC.exists() and str(MCP_SRC) not in sys.path:
    sys.path.insert(0, str(MCP_SRC))


def _maybe_reexec_under_venv() -> None:
    """Auto-promote to the project venv's Python if not already there.

    Same self-bootstrap pattern as scripts/normalize_jira_story.py: a
    single `python scripts/verify_mcp.py` command works on every OS
    because we re-exec under `.venv/bin/python` (Unix) or
    `.venv\\Scripts\\python.exe` (Windows) when needed. Silently no-op
    if the venv doesn't exist yet."""
    if os.environ.get("_VERIFY_VENV_BOOTSTRAPPED"):
        return

    if sys.platform == "win32":
        venv_python = (
            REPO_ROOT / "drawio-mcp-server" / ".venv" / "Scripts" / "python.exe"
        )
    else:
        venv_python = REPO_ROOT / "drawio-mcp-server" / ".venv" / "bin" / "python"

    if not venv_python.exists():
        return

    try:
        already_in_venv = (
            Path(sys.executable).resolve() == venv_python.resolve()
        )
    except (OSError, RuntimeError):
        already_in_venv = False
    if already_in_venv:
        return

    new_env = dict(os.environ)
    new_env["_VERIFY_VENV_BOOTSTRAPPED"] = "1"
    argv = [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]]

    if sys.platform == "win32":
        import subprocess

        completed = subprocess.run(argv, env=new_env)
        sys.exit(completed.returncode)
    else:
        os.execve(str(venv_python), argv, new_env)


_maybe_reexec_under_venv()


EXPECTED_TOOLS = (
    "list_diagrams",
    "read_diagram",
    "read_diagram_summary",
    "create_diagram",
    "add_title",
    "add_container",
    "add_node",
    "add_edge",
    "add_connector_table",
    "update_node",
    "remove_element",
    "list_stories",
    "read_story",
)


# ---------------------------------------------------------------------------
# Server health
# ---------------------------------------------------------------------------


def check_server_registry() -> tuple[bool, list[str], list[str]]:
    """Import the MCP tool registry and confirm every expected tool is
    present. Returns (ok, advertised_names, missing_names)."""
    try:
        from drawio_mcp_server.tools import all_tool_definitions
    except ImportError as exc:
        return False, [], [f"import error: {exc}"]

    try:
        tools = all_tool_definitions()
    except Exception as exc:
        return False, [], [f"registry build failed: {exc}"]

    names = [t.name for t in tools]
    missing = [n for n in EXPECTED_TOOLS if n not in names]
    return (not missing) and len(names) >= len(EXPECTED_TOOLS), names, missing


# ---------------------------------------------------------------------------
# Diagram structural checks
# ---------------------------------------------------------------------------


def check_diagram(name: str, diagrams_dir: Path, icons_root: Path, strict: bool) -> tuple[bool, list[str], list[str]]:
    """Load a diagram and run structural checks.

    Returns (ok, errors, warnings). `errors` always cause non-zero exit.
    `warnings` only fail when `strict=True`."""
    try:
        from drawio_mcp_server.drawio.gcp_icons import detect_icon_from_label
        from drawio_mcp_server.util.diagram_store import DiagramStore
    except ImportError as exc:
        return False, [f"import error: {exc}"], []

    store = DiagramStore(diagrams_dir.resolve())
    if not store.exists(name):
        return False, [f"diagram not found under {diagrams_dir}: {name}"], []

    diagram = store.load(name)
    errors: list[str] = []
    warnings: list[str] = []

    # 1) No dangling edges.
    node_ids = {n.id for n in diagram.nodes}
    for e in diagram.edges:
        if e.source_id not in node_ids:
            errors.append(
                f"dangling edge {e.id}: source id {e.source_id!r} not in node set"
            )
        if e.target_id not in node_ids:
            errors.append(
                f"dangling edge {e.id}: target id {e.target_id!r} not in node set"
            )

    # 1b) Arrow rendering check. Walks the raw .drawio XML and inspects
    #     each edge cell's style attribute directly (the in-memory
    #     DiagramEdge model doesn't preserve the full style string).
    #     An edge missing endArrow or having endArrow=none renders as
    #     a bare line with no direction indicator — broken UX.
    arrow_errors, parallel_warnings = _check_edges_in_xml(diagrams_dir, name)
    errors.extend(arrow_errors)
    warnings.extend(parallel_warnings)

    # 2) No duplicate node labels (warning — sometimes intentional, e.g.
    #    two distinct Pub/Sub topics — but usually a sign of a half-done
    #    rename or split). Embedded-table cells (id prefix `ctbl_`) are
    #    excluded — repeated values like "{TBD}", "Source", "Target"
    #    across table rows aren't structural duplicates.
    label_counts = Counter(
        n.label
        for n in diagram.nodes
        if n.label and not n.id.startswith("ctbl_")
    )
    for label, count in label_counts.items():
        if count > 1:
            warnings.append(f"duplicate node label {label!r} appears {count}x")

    # 3) GCP services that aren't using their official icon. A node is
    #    flagged when its label heuristically resolves to a known GCP
    #    service name (per `detect_icon_from_label`) but the node has no
    #    `raw_style` — i.e. it's still a generic stencil shape. Skip
    #    layer/zone containers (swimlanes / plain containers) — those
    #    are background frames whose label may legitimately mention a
    #    service category without needing an icon.
    for n in diagram.nodes:
        if n.raw_style:
            continue  # already using an icon style
        if n.shape in ("container", "swimlane"):
            continue  # background frame, not a component
        suggested = detect_icon_from_label(n.label)
        if suggested:
            warnings.append(
                f"node {n.id} {n.label!r} looks like a GCP service "
                f"({suggested!r}) but is not using the GCP icon — "
                f"consider update_node(..., gcp_icon={suggested!r})"
            )

    fatal = bool(errors) or (strict and warnings)
    return (not fatal), errors, warnings


def _check_edges_in_xml(
    diagrams_dir: Path, name: str
) -> tuple[list[str], list[str]]:
    """Walk the raw .drawio XML and inspect each edge's style attribute.
    Returns (arrow_errors, parallel_warnings).

    Two distinct checks (combined here so we only parse the XML once):

    Arrow-rendering errors (always fatal):
      - edge has no `style` attribute
      - style omits `endArrow=`
      - `endArrow=none`
      - `endArrow` set but `endFill=` missing or 0 (arrowhead present
        but unfilled — invisible in most renderers)

    Parallel-edge warnings (fatal under --strict):
      - 2+ edges share the same source AND the same target, but the
        edges DON'T have distinct entryY / exitY fractions → they'll
        render stacked, hard to tell apart
      - 2+ edges share a single endpoint (source OR target) without
        any `exitY` / `entryY` fan-out applied → they'll likely
        overlap somewhere on the orthogonal route
    """
    import xml.etree.ElementTree as ET

    path = (diagrams_dir / (name if name.endswith(".drawio") else name + ".drawio")).resolve()
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as exc:
        return [f"could not parse {path.name} for edge check: {exc}"], []

    arrow_errors: list[str] = []
    parallel_warnings: list[str] = []

    # Collect each edge: (id, source, target, parsed_style_dict)
    edges: list[tuple[str, str, str, dict[str, str]]] = []
    for cell in tree.iter("mxCell"):
        if cell.attrib.get("edge") != "1":
            continue
        edge_id = cell.attrib.get("id", "?")
        src = cell.attrib.get("source", "")
        tgt = cell.attrib.get("target", "")
        style = cell.attrib.get("style", "")
        style_dict = _parse_style_string(style)

        # --- Arrow check ---
        if not style:
            arrow_errors.append(
                f"edge {edge_id} has no `style` attribute — arrowhead "
                f"won't render"
            )
        else:
            if "endArrow" not in style_dict:
                arrow_errors.append(
                    f"edge {edge_id} style is missing `endArrow=` — arrow "
                    f"may not render in webview / VS Code extension"
                )
            elif style_dict["endArrow"].lower() == "none":
                arrow_errors.append(
                    f"edge {edge_id} has `endArrow=none` — no arrowhead "
                    f"will render (was this intentional? if yes, mark the "
                    f"edge with step=0 to suppress validation)"
                )
            if style_dict.get("endArrow", "").lower() not in ("", "none"):
                if "endFill" not in style_dict:
                    arrow_errors.append(
                        f"edge {edge_id} sets endArrow but omits "
                        f"`endFill=1` — arrowhead may render as a "
                        f"hairline outline only"
                    )
                elif style_dict["endFill"].strip() == "0":
                    arrow_errors.append(
                        f"edge {edge_id} has `endFill=0` — arrowhead "
                        f"will render unfilled (effectively invisible)"
                    )

        edges.append((edge_id, src, tgt, style_dict))

    # --- Parallel-edge / overlap check ---
    # Group by source and by target
    by_source: dict[str, list[tuple[str, str, str, dict[str, str]]]] = {}
    by_target: dict[str, list[tuple[str, str, str, dict[str, str]]]] = {}
    by_pair: dict[tuple[str, str], list[tuple[str, str, str, dict[str, str]]]] = {}
    for rec in edges:
        eid, src, tgt, _ = rec
        by_source.setdefault(src, []).append(rec)
        by_target.setdefault(tgt, []).append(rec)
        by_pair.setdefault((src, tgt), []).append(rec)

    # Exact-duplicate pairs (same source AND same target) must have
    # distinct entry/exit Y fractions, otherwise they render exactly on
    # top of each other.
    for (src, tgt), siblings in by_pair.items():
        if len(siblings) < 2:
            continue
        entry_ys = {s[3].get("entryY", "") for s in siblings}
        exit_ys = {s[3].get("exitY", "") for s in siblings}
        if len(entry_ys) == 1 and len(exit_ys) == 1:
            parallel_warnings.append(
                f"{len(siblings)} edges share endpoints {src} → {tgt} "
                f"with identical entry/exit fractions — they will "
                f"render stacked. Ids: "
                f"{', '.join(s[0] for s in siblings)}"
            )

    # Fan-in / fan-out without spread: 2+ edges into the same target
    # (or out of the same source) sharing the same entry/exit Y will
    # overlap on the orthogonal route.
    for tgt, siblings in by_target.items():
        if len(siblings) < 2:
            continue
        entry_ys = {s[3].get("entryY", "") for s in siblings}
        if len(entry_ys) == 1:
            parallel_warnings.append(
                f"{len(siblings)} edges fan INTO {tgt!r} but share the "
                f"same entryY (no fan-out) — orthogonal router will "
                f"stack them. Ids: {', '.join(s[0] for s in siblings)}"
            )

    for src, siblings in by_source.items():
        if len(siblings) < 2:
            continue
        exit_ys = {s[3].get("exitY", "") for s in siblings}
        if len(exit_ys) == 1:
            parallel_warnings.append(
                f"{len(siblings)} edges fan OUT of {src!r} but share "
                f"the same exitY (no fan-out) — orthogonal router will "
                f"stack them. Ids: {', '.join(s[0] for s in siblings)}"
            )

    return arrow_errors, parallel_warnings


def _parse_style_string(style: str) -> dict[str, str]:
    """Parse a drawio style string ('k1=v1;k2=v2;...') into a dict.
    Whitespace tolerant; ignores empty segments produced by trailing
    semicolons."""
    out: dict[str, str] = {}
    for chunk in style.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            # standalone style keyword (e.g. 'ellipse', 'shape=cloud')
            out.setdefault(chunk, "1")
            continue
        k, _, v = chunk.partition("=")
        out[k.strip()] = v.strip()
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Server + diagram health check. Cross-platform: same "
            "command works on macOS / Linux / Windows."
        )
    )
    parser.add_argument(
        "--diagram",
        default=None,
        help=(
            "Diagram filename (under --diagrams-dir) to run structural "
            "checks against. Omit to check only the MCP server."
        ),
    )
    parser.add_argument(
        "--diagrams-dir",
        type=Path,
        default=DEFAULT_DIAGRAMS_DIR,
        help=f"Diagrams root (default: {DEFAULT_DIAGRAMS_DIR}).",
    )
    parser.add_argument(
        "--icons-dir",
        type=Path,
        default=DEFAULT_ICONS_DIR,
        help=f"GCP icons root (default: {DEFAULT_ICONS_DIR}).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Treat warnings (duplicate labels, missing GCP icons) as "
            "failures."
        ),
    )
    args = parser.parse_args(argv)

    # 1) Server registry.
    print("[verify] checking MCP server tool registry…")
    server_ok, names, missing = check_server_registry()
    print(f"[verify]   tools advertised: {len(names)}")
    for n in names:
        print(f"[verify]     - {n}")
    if missing:
        print(f"[verify]   MISSING: {', '.join(missing)}")
    if not server_ok:
        print("[verify] SERVER CHECK FAILED.", file=sys.stderr)
        return 2
    print("[verify]   ✓ server registry OK")

    # 2) Optional diagram structural checks.
    if args.diagram:
        print(f"[verify] checking diagram {args.diagram}…")
        diagram_ok, errors, warnings = check_diagram(
            args.diagram,
            args.diagrams_dir,
            args.icons_dir,
            args.strict,
        )
        for err in errors:
            print(f"[verify]   ERROR: {err}", file=sys.stderr)
        for warn in warnings:
            print(f"[verify]   warning: {warn}")
        if not diagram_ok:
            print("[verify] DIAGRAM CHECK FAILED.", file=sys.stderr)
            return 2
        if warnings and not args.strict:
            print(
                "[verify]   ✓ diagram structurally sound "
                "(warnings present — re-run with --strict to fail on them)"
            )
        else:
            print("[verify]   ✓ diagram structurally sound")

    print("[verify] all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
