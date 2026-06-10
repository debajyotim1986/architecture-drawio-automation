from __future__ import annotations

from typing import Any

from mcp.types import Tool

from ..types import DiagramEdge, DiagramNode
from ..util.config import ServerConfig
from ..util.diagram_store import DiagramStore

add_edge_tool = Tool(
    name="add_edge",
    description=(
        "Connect two existing nodes with a directed edge. Source and target "
        "may be specified by node id OR by exact label match. Optional label "
        "describes the relationship (e.g. 'HTTPS', 'publishes', 'reads'). "
        "Every edge automatically gets a 1-based step number rendered as a "
        "small colored circle on its midpoint — useful for showing data-flow "
        "ordering. The server auto-assigns the next number; pass `step` "
        "explicitly only if you need a specific ordering (e.g. branching). "
        "Pass `step=0` (or any value ≤ 0) to suppress the badge."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "diagram": {"type": "string"},
            "from": {"type": "string", "description": "Source: node id or exact label."},
            "to": {"type": "string", "description": "Target: node id or exact label."},
            "label": {"type": "string"},
            "id": {"type": "string", "description": "Optional edge id; auto-generated if omitted."},
            "step": {
                "type": "integer",
                "description": (
                    "Optional 1-based sequence number for the step badge. "
                    "Auto-assigned (= max existing step + 1) when omitted. "
                    "Pass 0 or a negative value to suppress the badge."
                ),
            },
        },
        "required": ["diagram", "from", "to"],
        "additionalProperties": False,
    },
)


async def add_edge(args: dict[str, Any], cfg: ServerConfig) -> dict[str, str]:
    diagram_name = str(args.get("diagram") or "")
    src = str(args.get("from") or "")
    dst = str(args.get("to") or "")
    if not diagram_name or not src or not dst:
        raise ValueError("`diagram`, `from`, and `to` are required.")

    store = DiagramStore(cfg.diagrams_dir)
    diagram = store.load(diagram_name)

    source_id = _resolve(diagram.nodes, src)
    target_id = _resolve(diagram.nodes, dst)

    edge_id = str(args.get("id") or _next_edge_id([e.id for e in diagram.edges]))

    # Resolve step_index: explicit positive value wins; explicit ≤0
    # suppresses the badge; otherwise auto-assign one higher than the
    # current maximum step on the diagram (sequence-numbering that
    # survives independent edge ids / id reuse).
    if "step" in args and args["step"] is not None:
        try:
            requested = int(args["step"])
        except (TypeError, ValueError):
            requested = None
        step_index: int | None = requested if (requested or 0) > 0 else None
    else:
        existing_steps = [
            e.step_index for e in diagram.edges if e.step_index is not None
        ]
        step_index = (max(existing_steps) + 1) if existing_steps else 1

    diagram.edges.append(
        DiagramEdge(
            id=edge_id,
            source_id=source_id,
            target_id=target_id,
            label=str(args["label"]) if args.get("label") else None,
            step_index=step_index,
        )
    )

    # Fan out parallel edges: any time 2+ edges share a source OR a
    # target, drawio's orthogonal router happily stacks them on top
    # of each other (same line, same arrowhead, overlapping labels).
    # Spreading their exit/entry fractions across the node perimeter
    # gives the router enough room to route them in parallel.
    _distribute_parallel_endpoints(diagram)

    # Compute explicit waypoints so cross-container edges route
    # through known-empty row gaps and never draw over an icon in
    # an intermediate swimlane. Drawio's default orthogonal router
    # is obstacle-aware but heuristic — explicit waypoints turn the
    # "tries to avoid" into "MUST go through these points".
    _compute_waypoints(diagram)

    # Deconflict edges that ended up on identical (or x-overlapping)
    # horizontal segments at the same highway-y — without this pass,
    # two edges with no shared endpoint can still collapse to the same
    # waypoint pair (and therefore the same midpoint label position).
    _deconflict_highway_lanes(diagram)

    # Frame icons that take 4+ connectors in a visible "card" border —
    # the box tells the reader "this is a busy node" and gives the
    # surrounding connector labels a non-icon edge to butt up against.
    _frame_busy_nodes(diagram)

    result: dict[str, Any] = {"id": edge_id, "path": store.save(diagram_name, diagram)}
    if step_index is not None:
        result["step"] = step_index
    return result


def _resolve(nodes: list[DiagramNode], ref: str) -> str:
    for n in nodes:
        if n.id == ref:
            return n.id
    for n in nodes:
        if n.label == ref:
            return n.id
    raise ValueError(f"No node matches '{ref}' (tried id and label).")


def _next_edge_id(existing: list[str]) -> str:
    taken = set(existing)
    i = 1
    while f"e{i}" in taken:
        i += 1
    return f"e{i}"


# Geometry for parallel-edge fan-out. Endpoints (entryX/Y, exitX/Y) are
# expressed as fractions of the target/source node's bounding box —
# (0, 0) = top-left, (1, 1) = bottom-right.
#
# Assumption: data flows left → right in our swimlane layout, so edges
# enter the LEFT side of the target and exit the RIGHT side of the
# source. For a fan of N siblings sharing one endpoint, we spread the
# OTHER axis (Y) symmetrically around 0.5 so they don't stack.
_FAN_OUT_SPREAD = 0.6  # full vertical range used for fanning (0.2..0.8)


def _distribute_parallel_endpoints(diagram: Any) -> None:
    """Set per-edge exit/entry endpoint fractions:
      - Direction-aware exitX / entryX based on relative positions of
        source and target (forward edges exit RIGHT, enter LEFT;
        backward edges exit LEFT, enter RIGHT — avoids long detour
        loops in the orthogonal router).
      - Spread exitY / entryY across the node's perimeter when 2+
        edges share an endpoint, so they don't stack on the same line.

    Idempotent: clears any stale fan-out keys first so a later
    add_edge can rebalance a fan that shrunk back to 1 sibling.
    """
    by_id = {n.id: n for n in diagram.nodes}

    # Build sibling groups.
    by_source: dict[str, list[Any]] = {}
    by_target: dict[str, list[Any]] = {}
    for e in diagram.edges:
        by_source.setdefault(e.source_id, []).append(e)
        by_target.setdefault(e.target_id, []).append(e)

    # Clear stale fan-out style keys before recomputing.
    fan_keys = ("exitX", "exitY", "entryX", "entryY")
    for e in diagram.edges:
        for k in fan_keys:
            e.style.pop(k, None)

    # Set direction-aware exit/entry X for cross-container edges.
    # For edges within the same container, leave the router free.
    for e in diagram.edges:
        src = by_id.get(e.source_id)
        tgt = by_id.get(e.target_id)
        if not src or not tgt:
            continue
        if src.parent_id is not None and src.parent_id == tgt.parent_id:
            continue
        sx, _, _, _ = _abs_position(src, by_id)
        tx, _, _, _ = _abs_position(tgt, by_id)
        # "Forward" = target is to the right of source (the usual L→R
        # flow). "Backward" = target is to the left. The latter would
        # draw an ugly loop if we forced exit RIGHT / enter LEFT, so
        # mirror it: exit LEFT / enter RIGHT.
        if sx <= tx:
            e.style["exitX"] = "1"
            e.style["entryX"] = "0"
        else:
            e.style["exitX"] = "0"
            e.style["entryX"] = "1"

    # Fan out exits (source side).
    for source_id, siblings in by_source.items():
        if len(siblings) < 2:
            continue
        # Order by step_index so the fan is deterministic across runs.
        ordered = sorted(
            siblings,
            key=lambda e: (e.step_index if e.step_index is not None else 10**6),
        )
        for i, edge in enumerate(ordered):
            edge.style["exitY"] = f"{_fan_offset(i, len(ordered)):.2f}"

    # Fan out entries (target side).
    for target_id, siblings in by_target.items():
        if len(siblings) < 2:
            continue
        ordered = sorted(
            siblings,
            key=lambda e: (e.step_index if e.step_index is not None else 10**6),
        )
        for i, edge in enumerate(ordered):
            edge.style["entryY"] = f"{_fan_offset(i, len(ordered)):.2f}"


def _abs_position(node: Any, by_id: dict[str, Any]) -> tuple[float, float, float, float]:
    """Return absolute (x, y, w, h) by walking the parent_id chain.

    Nested-child coordinates in our model are RELATIVE to the
    container; this function adds up the ancestor chain so we can
    reason about real diagram positions for routing decisions.
    """
    x, y = float(node.x), float(node.y)
    p = node.parent_id
    while p:
        parent = by_id.get(p)
        if not parent:
            break
        x += float(parent.x)
        y += float(parent.y)
        p = parent.parent_id
    return x, y, float(node.width), float(node.height)


# Layout constants — must match the values in
# tools/add_node.py (_CONTAINER_CHILD_Y0, _CONTAINER_CHILD_STRIDE)
# and drawio/shapes.py (swimlane height + icon height 64).
# Centralised here for the waypoint maths.
_DIAGRAM_Y_ORIGIN = 40.0       # container top y
_HEADER_HEIGHT = 30.0          # swimlane header strip
_FIRST_CHILD_Y = 50.0          # offset of first child inside container
_CHILD_STRIDE = 200.0          # vertical distance between children
_ICON_HEIGHT = 64.0
_ICON_LABEL_BAND = 16.0        # height of the "Cloud Composer" text below an icon
# How far the waypoint corridor sits into the column gap. Should be
# half the column gap so vertical lines run down the centerline of
# the gap between containers — must stay in sync with `_COLUMN_GAP`
# in tools/add_container.py (currently 140 → inset 70).
_CORRIDOR_INSET = 70.0

# Row-gap horizontal "highway" lanes that the waypoint router uses.
# Each lane sits in the empty vertical strip between two icon rows,
# OFFSET DOWNWARD from the geometric midpoint so connector labels
# (rendered ABOVE the line, with extra y-offset for clarity) stay
# below the icon-name label band of the row above.
#
# Layout (stride 200):
#   Icon row 0 abs y:    40 + 50 = 90   ..  90 + 64  = 154
#   Icon-name label   ~ 154         ..  154 + 16 = 170
#   Icon row 1 abs y:    40 + 250 = 290 ..  290 + 64 = 354
#   Safe corridor:        170 + 6 = 176 ..  290 - 6  = 284  (108 px tall)
#   Highway base y:       (176 + 284) / 2 = 230
#   Highway k:            230 + 200*k
_ROW_GAP_BASE_Y = 230.0
_ROW_GAP_STRIDE = 200.0
_FIRST_ROW_TOP_Y = (
    _DIAGRAM_Y_ORIGIN + _HEADER_HEIGHT + 5.0
)  # 75: just below header, usable as a "top highway" if needed


def _nearest_safe_highway_y(desired_y: float) -> float:
    """Snap `desired_y` to the nearest row-gap midpoint — a y-coord
    that sits between icon rows, so a horizontal edge segment there
    can cross any number of swimlanes without touching an icon."""
    k = round((desired_y - _ROW_GAP_BASE_Y) / _ROW_GAP_STRIDE)
    if k < 0:
        # Above the first icon row — use the small margin under the
        # swimlane header. Tight but icon-free.
        return _FIRST_ROW_TOP_Y
    return _ROW_GAP_BASE_Y + k * _ROW_GAP_STRIDE


def _compute_waypoints(diagram: Any) -> None:
    """Set explicit waypoints for every nested edge so the orthogonal
    router never draws through an intermediate icon. Idempotent —
    clears previous waypoints before recomputing.

    Two routing modes:

    1. Cross-container (different parent_id, or one/both top-level):
       exit → (corridor_after_src, highway_y) → (corridor_before_tgt, highway_y) → entry
       where `highway_y` snaps to the nearest icon-row gap so the
       horizontal segment crosses every intermediate swimlane through
       empty vertical space (no icon in any column at that y).

    2. Same-container (src.parent_id == tgt.parent_id, both nested in
       the same swimlane). The default router would draw a vertical
       line in the column — which CROSSES any icon between source row
       and target row. Fix: route THROUGH THE GAP to the right of the
       container. Exit source's right side → corridor in the column
       gap → vertical segment in that gap → corridor → enter target's
       right side. The icons in between stay clear because the
       vertical lives in the empty corridor between this swimlane and
       the next, not inside the swimlane.
    """
    by_id = {n.id: n for n in diagram.nodes}

    for edge in diagram.edges:
        edge.waypoints = []

        src = by_id.get(edge.source_id)
        tgt = by_id.get(edge.target_id)
        if not src or not tgt:
            continue
        # Both endpoints must be inside a container to apply our
        # routing logic; top-level floating nodes are handled by the
        # default router.
        if not src.parent_id or not tgt.parent_id:
            continue

        sx, sy, sw, sh = _abs_position(src, by_id)
        tx, ty, tw, th = _abs_position(tgt, by_id)
        exit_y_frac = float(edge.style.get("exitY", "0.5"))
        entry_y_frac = float(edge.style.get("entryY", "0.5"))
        exit_y_abs = sy + sh * exit_y_frac
        entry_y_abs = ty + th * entry_y_frac

        if src.parent_id == tgt.parent_id:
            # SAME-CONTAINER routing. Route in the column gap to the
            # RIGHT of the container so the vertical segment never
            # crosses any icon stacked in this column. Endpoints both
            # exit from the right side of source / enter the right
            # side of target.
            container = by_id.get(src.parent_id)
            if container is None:
                continue
            cx, cy, cw, ch = _abs_position(container, by_id)
            # Lane sits in the column gap (column-gap width ≈ 80; we
            # take 40 in for a clean visual separation from the
            # container edge).
            lane_x = cx + cw + _CORRIDOR_INSET
            # Force exit/entry from the right side of the icon at the
            # configured Y fraction.
            edge.style["exitX"] = "1"
            edge.style["entryX"] = "1"
            edge.style.setdefault("exitY", "0.5")
            edge.style.setdefault("entryY", "0.5")
            edge.waypoints = [
                (lane_x, exit_y_abs),
                (lane_x, entry_y_abs),
            ]
            continue

        # CROSS-CONTAINER routing (existing logic).
        exit_x_frac = float(edge.style.get("exitX", "1"))
        entry_x_frac = float(edge.style.get("entryX", "0"))
        if exit_x_frac > 0.5:
            corridor_after_src = sx + sw + _CORRIDOR_INSET
        else:
            corridor_after_src = sx - _CORRIDOR_INSET
        if entry_x_frac < 0.5:
            corridor_before_tgt = tx - _CORRIDOR_INSET
        else:
            corridor_before_tgt = tx + tw + _CORRIDOR_INSET

        midpoint_y = (exit_y_abs + entry_y_abs) / 2.0
        highway_y = _nearest_safe_highway_y(midpoint_y)

        wp1 = (corridor_after_src, highway_y)
        wp2 = (corridor_before_tgt, highway_y)
        if wp1 == wp2:
            edge.waypoints = [wp1]
        else:
            edge.waypoints = [wp1, wp2]


def _fan_offset(index: int, total: int) -> float:
    """Spread `total` siblings evenly across [0.5 - SPREAD/2, 0.5 + SPREAD/2].
    Returns the Y-fraction for the `index`-th sibling (0-based)."""
    if total <= 1:
        return 0.5
    start = 0.5 - _FAN_OUT_SPREAD / 2
    step = _FAN_OUT_SPREAD / (total - 1)
    return start + index * step


# Maximum Y excursion (px) from the highway centre. The full safe band
# is therefore ±_LANE_BAND_HALF. With stride 200, the row gap between
# two icon rows is 136 px (200 - 64) — minus the 16-px icon-label band
# of the row above and a 6-px clearance, the safe corridor is ~108 px
# wide. Setting band-half to 50 keeps 7 stacked sub-lanes at 16-17 px
# spacing — wide enough that a 12-px-tall connector label sits clear
# of the next sub-lane's label.
_LANE_BAND_HALF = 50.0


def _sub_lane_offsets(n: int) -> list[float]:
    """Return `n` Y offsets symmetrically spread across the safe band.

    - n=1 → [0.0] (no deconfliction needed).
    - n=2 → [-12, +12] (small visual nudge for the common case).
    - n≥3 → evenly distributed across [-band_half, +band_half]
      inclusive, e.g. n=5 → [-36, -18, 0, +18, +36].

    Unlike a fixed-modulo offset table, this guarantees every member of
    a cluster of size n gets a UNIQUE offset — so we never re-create
    the very collision we're trying to eliminate when the cluster is
    bigger than the offset table.
    """
    if n <= 1:
        return [0.0]
    if n == 2:
        third = _LANE_BAND_HALF / 3.0
        return [-third, third]
    step = (2.0 * _LANE_BAND_HALF) / (n - 1)
    return [-_LANE_BAND_HALF + i * step for i in range(n)]


def _deconflict_highway_lanes(diagram: Any) -> None:
    """Post-pass for `_compute_waypoints`. When 2+ cross-container
    edges produce horizontal waypoint segments that share both their
    highway-y AND an overlapping x-range, push them onto distinct
    sub-lanes within the same icon-row gap so their lines and labels
    no longer sit on top of one another.

    Why this is needed:
    - `_distribute_parallel_endpoints` only fans edges that share a
      source OR a target node. Two edges with no shared endpoint can
      still route through the same horizontal corridor (same gap
      between two icon rows, same lane between two columns) and end
      up with byte-identical waypoint pairs.
    - The midpoint label `"N. <label>"` sits at the geometric centre
      of the line, so identical lines → labels stacked on top.

    Sub-lanes are sized so the line + label stay within the row gap
    between the icon row above and the icon row below the highway —
    we never introduce a new edge-vs-icon overlap to fix an
    edge-vs-edge overlap.
    """
    candidates: list[tuple[Any, float, float, float]] = []
    for e in diagram.edges:
        if len(e.waypoints) != 2:
            continue
        (x1, y1), (x2, y2) = e.waypoints
        if abs(y1 - y2) > 0.5:
            continue  # Not a horizontal segment.
        candidates.append((e, min(x1, x2), max(x1, x2), y1))

    by_y: dict[float, list[tuple[Any, float, float]]] = {}
    for e, lx, rx, y in candidates:
        by_y.setdefault(round(y, 1), []).append((e, lx, rx))

    for highway_y, members in by_y.items():
        # Sweep-line cluster: members whose x-intervals overlap form
        # one group needing deconfliction. Non-overlapping intervals
        # on the same y are fine (different parts of the diagram).
        members.sort(key=lambda m: m[1])
        clusters: list[list[tuple[Any, float, float]]] = []
        current: list[tuple[Any, float, float]] = []
        current_right = -float("inf")
        for m in members:
            _, lx, rx = m
            if lx > current_right + 0.5:
                if current:
                    clusters.append(current)
                current = [m]
                current_right = rx
            else:
                current.append(m)
                current_right = max(current_right, rx)
        if current:
            clusters.append(current)

        for cluster in clusters:
            if len(cluster) < 2:
                continue
            # Sort deterministically by step_index so re-runs produce
            # identical sub-lane assignments (idempotent fix).
            cluster.sort(
                key=lambda c: (
                    c[0].step_index if c[0].step_index is not None else 10**6,
                    c[0].id,
                )
            )
            offsets = _sub_lane_offsets(len(cluster))
            for (edge, _, _), offset in zip(cluster, offsets):
                if offset == 0.0:
                    continue
                new_y = highway_y + offset
                (x1, _), (x2, _) = edge.waypoints
                edge.waypoints = [(x1, new_y), (x2, new_y)]


# A node with this many edges (in + out) is "busy" — we frame it.
_BUSY_DEGREE_THRESHOLD = 3

# Style fragments injected into a busy icon's raw_style. drawio renders
# shape=image with the image filling the cell box; adding strokeColor +
# strokeWidth draws a visible border around the box, and rounded=1
# softens the corners. The fill is ignored under the opaque image, but
# we set it anyway so future style changes (e.g. transparent icons)
# still show a card.
_BUSY_FRAME_STYLE = (
    "rounded=1;arcSize=18;"
    "strokeColor=#5F6368;strokeWidth=1.5;"
    "fillColor=#FAFAFA;"
)


def _frame_busy_nodes(diagram: Any) -> None:
    """Mark icons with degree > _BUSY_DEGREE_THRESHOLD as 'busy' by
    injecting a visible rounded-border frame into their raw_style.

    Why: when a single icon serves as the source or target for many
    connectors, its surrounding area gets crowded with labels. A
    framed card around the icon (a) signals visually that this is a
    hub node, and (b) gives connector labels a clear non-icon edge to
    butt against — preventing visual confusion between icon-name
    labels and connector labels.

    The pass is idempotent: re-injecting the same fragment is a no-op
    because each style key is set just once."""
    degree: dict[str, int] = {}
    for e in diagram.edges:
        degree[e.source_id] = degree.get(e.source_id, 0) + 1
        degree[e.target_id] = degree.get(e.target_id, 0) + 1

    for node in diagram.nodes:
        d = degree.get(node.id, 0)
        if d <= _BUSY_DEGREE_THRESHOLD:
            continue
        # Only frame icon-style nodes (shape=image with embedded SVG).
        # Stencil shapes (cylinder, swimlane, etc.) already have their
        # own border and don't need decoration.
        if not node.raw_style or "shape=image" not in node.raw_style:
            continue
        for kv in _BUSY_FRAME_STYLE.rstrip(";").split(";"):
            if not kv:
                continue
            key = kv.split("=", 1)[0] + "="
            if key in node.raw_style:
                continue  # respect any caller-provided override
            if not node.raw_style.endswith(";"):
                node.raw_style += ";"
            node.raw_style += kv + ";"
