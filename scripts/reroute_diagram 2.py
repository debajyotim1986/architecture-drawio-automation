#!/usr/bin/env python3
"""Re-run the routing + layout passes on an existing .drawio file.

Use this after a routing or layout change so existing diagrams pick up
the new logic without a full add_node / add_edge replay through the MCP
server. Idempotent: running it on an already-correct diagram is a no-op
(positions and waypoints get recomputed to the same values).

What it does, in order:
  1. Re-snap swimlane containers onto the current `_COLUMN_GAP` so
     they spread on the current column stride.
  2. Re-snap container children onto the current `_CONTAINER_CHILD_STRIDE`
     so layout matches whatever the current source code defines.
  3. Re-fan parallel edge endpoints (`_distribute_parallel_endpoints`).
  4. Re-compute explicit waypoints (`_compute_waypoints`).
  5. Deconflict edges that ended up sharing a horizontal lane
     (`_deconflict_highway_lanes`).
  6. Apply busy-node framing for icons with >3 connectors
     (`_frame_busy_nodes`).

Note: legacy connector-detail tables embedded in the diagram are not
re-scaled — they sit below the swimlanes and a small horizontal
misalignment after a column-gap change is cosmetic. Regenerate the
table with `scripts/generate_connector_details.py` +
`add_connector_table` if you want pixel-perfect alignment.

Usage:
  python scripts/reroute_diagram.py <diagram-name-or-path>

Example:
  python scripts/reroute_diagram.py PROJ-127-20260527-064207.drawio
"""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_SRC = REPO_ROOT / "drawio-mcp-server" / "src"
DIAGRAMS_DIR = REPO_ROOT / "diagrams"


def _venv_python() -> Path | None:
    for candidate in (
        REPO_ROOT / "drawio-mcp-server" / ".venv" / "bin" / "python",
        REPO_ROOT / ".venv" / "bin" / "python",
        REPO_ROOT / "drawio-mcp-server" / ".venv" / "Scripts" / "python.exe",
        REPO_ROOT / ".venv" / "Scripts" / "python.exe",
    ):
        if candidate.exists():
            return candidate
    return None


def _ensure_under_venv() -> None:
    venv_py = _venv_python()
    if venv_py is None:
        return
    if Path(sys.executable).resolve() == venv_py.resolve():
        return
    os.execve(str(venv_py), [str(venv_py), __file__, *sys.argv[1:]], os.environ)


_ensure_under_venv()

sys.path.insert(0, str(SERVER_SRC))

from drawio_mcp_server.tools.add_edge import (  # noqa: E402
    _compute_waypoints,
    _deconflict_highway_lanes,
    _distribute_parallel_endpoints,
    _frame_busy_nodes,
)
from drawio_mcp_server.tools.add_container import (  # noqa: E402
    _COLUMN_GAP,
    _COLUMN_ORIGIN_X,
    _COLUMN_ORIGIN_Y,
)
from drawio_mcp_server.tools.add_node import (  # noqa: E402
    _CONTAINER_CHILD_STRIDE,
    _CONTAINER_CHILD_Y0,
)
from drawio_mcp_server.util.diagram_store import DiagramStore  # noqa: E402


def _relayout_containers(diagram) -> None:
    """Re-snap swimlane containers onto the current column stride.

    Existing diagrams may have been authored with a different gap
    (e.g. 80 -> 140). Containers placed in left-to-right reading
    order get their x re-computed; explicit y/width/height are kept
    so the script doesn't accidentally overwrite hand-tuned layouts.
    """
    swimlanes = [n for n in diagram.nodes if n.shape == "swimlane"]
    # Sort by existing x so re-snap preserves the visual reading order.
    swimlanes.sort(key=lambda n: n.x)
    for i, lane in enumerate(swimlanes):
        lane.x = _COLUMN_ORIGIN_X + i * (lane.width + _COLUMN_GAP)
        # Keep the y/width/height the user (or earlier layout) chose.
        if lane.y == 0:
            lane.y = _COLUMN_ORIGIN_Y


def _relayout_children(diagram) -> None:
    """Re-snap each container's children onto the current row stride.

    Existing diagrams may have been authored with a different stride
    (e.g. 150 -> 200). When stride changes, child Y positions must be
    recomputed or edges will route through the new icon positions.
    """
    by_parent: dict[str, list] = {}
    declaration_order = {n.id: i for i, n in enumerate(diagram.nodes)}
    for node in diagram.nodes:
        if node.parent_id is None:
            continue
        # Only re-position children that look like row-stacked icons
        # (small bounding box). Larger nested children (e.g. tables)
        # keep their explicit Y.
        if node.height <= 96 and node.width <= 200:
            by_parent.setdefault(node.parent_id, []).append(node)

    for siblings in by_parent.values():
        # Preserve visual order: sort by existing Y, then declaration
        # order on tie. This survives reruns idempotently.
        siblings.sort(key=lambda n: (n.y, declaration_order[n.id]))
        for i, child in enumerate(siblings):
            child.y = _CONTAINER_CHILD_Y0 + i * _CONTAINER_CHILD_STRIDE


def _resolve_target(arg: str) -> tuple[Path, str]:
    """Return (diagrams_dir, diagram_name) for the given user input."""
    p = Path(arg)
    if p.is_absolute() or p.exists():
        full = p.resolve()
        return full.parent, full.name
    return DIAGRAMS_DIR, arg if arg.endswith(".drawio") else f"{arg}.drawio"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2

    diagrams_dir, name = _resolve_target(argv[1])
    store = DiagramStore(diagrams_dir)
    if not store.exists(name):
        print(f"error: diagram not found: {diagrams_dir / name}", file=sys.stderr)
        return 1

    src_path = diagrams_dir / name
    backup = src_path.with_suffix(src_path.suffix + ".bak")
    shutil.copy2(src_path, backup)

    diagram = store.load(name)
    before_positions = {n.id: (n.x, n.y) for n in diagram.nodes}
    before_waypoints = {e.id: list(e.waypoints) for e in diagram.edges}
    before_styles = {n.id: n.raw_style for n in diagram.nodes}

    _relayout_containers(diagram)
    _relayout_children(diagram)
    _distribute_parallel_endpoints(diagram)
    _compute_waypoints(diagram)
    _deconflict_highway_lanes(diagram)
    _frame_busy_nodes(diagram)

    stem = src_path.stem
    if "-" in stem and stem.split("-")[-1].isdigit():
        base = "-".join(stem.split("-")[:-2])
    else:
        base = stem
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    new_name = f"{base}-{timestamp}.drawio"
    store.save(new_name, diagram)

    moved = [
        n.id for n in diagram.nodes
        if before_positions.get(n.id) != (n.x, n.y)
    ]
    rerouted = [
        e.id for e in diagram.edges
        if before_waypoints.get(e.id) != list(e.waypoints)
    ]
    framed = [
        n.id for n in diagram.nodes
        if before_styles.get(n.id) != n.raw_style and n.raw_style
    ]
    print(f"backup:   {backup}")
    print(f"output:   {diagrams_dir / new_name}")
    print(f"nodes:    {len(diagram.nodes)}  moved:    {len(moved)}")
    print(f"edges:    {len(diagram.edges)}  rerouted: {len(rerouted)}")
    print(f"framed:   {len(framed)}  (degree > 3)")
    for nid in framed:
        n = next(x for x in diagram.nodes if x.id == nid)
        print(f"  {nid}: {n.label}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
