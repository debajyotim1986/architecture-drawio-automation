"""Parse a *.drawio file into our intent-level Diagram model.

Handles the unencoded/uncompressed mxfile variant. Real-world files may be
deflate+base64 inside <diagram> — extend this module before parsing those.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..types import Diagram, DiagramEdge, DiagramNode

# Edge labels emitted by the builder when step_index is set look like
# "1. uploads" / "12. writes audit". Pulling the number out here restores
# the structured step_index field on read so callers can reason about
# sequence without parsing labels themselves.
_STEP_PREFIX_RE = re.compile(r"^\s*(\d+)\.\s+(.*)$")


# Style keys we round-trip on edges. Anything in this set is captured
# from the .drawio XML on read and re-emitted on save so it survives
# the load/mutate/save cycle that happens on every MCP tool call. Keys
# outside this set are dropped (the DEFAULT_EDGE_STYLE is re-applied
# by the builder, so we don't need to preserve them explicitly).
_EDGE_PRESERVED_STYLE_KEYS = frozenset({
    "entryX",
    "entryY",
    "exitX",
    "exitY",
})


def _parse_style_attr(style: str) -> dict[str, str]:
    """Parse a drawio style string ('k1=v1;k2=v2;flag;...') into a dict."""
    out: dict[str, str] = {}
    for chunk in style.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            out.setdefault(chunk, "1")
            continue
        k, _, v = chunk.partition("=")
        out[k.strip()] = v.strip()
    return out


def parse_drawio(xml: str) -> Diagram:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError(f"Not valid XML: {exc}") from exc

    if root.tag != "mxfile":
        raise ValueError("Not a draw.io file: missing <mxfile> root.")

    diagram_el = root.find("diagram")
    if diagram_el is None:
        raise ValueError("Not a draw.io file: missing <diagram>.")

    name = diagram_el.attrib.get("name", "Untitled")
    model = diagram_el.find("mxGraphModel")
    if model is None:
        raise ValueError(
            "Diagram payload appears compressed/encoded. Save with "
            "Extras → Edit Diagram (uncompressed) before re-running."
        )

    cell_root = model.find("root")
    if cell_root is None:
        raise ValueError("Malformed diagram: missing <root>.")

    nodes: list[DiagramNode] = []
    edges: list[DiagramEdge] = []

    # First pass: collect the set of edge ids so the vertex loop below
    # can recognise step badges (vertex cells whose parent is an edge).
    # Order in the XML isn't guaranteed when a human edits the file in
    # drawio, so a two-pass approach is the only safe way.
    edge_ids: set[str] = set()
    for cell in cell_root.findall("mxCell"):
        if cell.attrib.get("edge") == "1":
            eid = cell.attrib.get("id", "")
            if eid:
                edge_ids.add(eid)

    # Step badges discovered while iterating vertex cells; applied to
    # the matching DiagramEdge after both passes.
    badge_by_edge_id: dict[str, int] = {}

    for cell in cell_root.findall("mxCell"):
        cell_id = cell.attrib.get("id", "")
        if cell_id in ("0", "1"):
            continue

        if cell.attrib.get("edge") == "1":
            raw_label = cell.attrib.get("value") or None
            # Parse "N. <label>" → (step_index=N, label=<label>). Falls
            # back to the legacy child-cell badge if no prefix found
            # (handled in the post-pass below).
            step_idx: int | None = None
            label_clean = raw_label
            if raw_label:
                m = _STEP_PREFIX_RE.match(raw_label)
                if m:
                    try:
                        step_idx = int(m.group(1))
                        label_clean = m.group(2).strip() or None
                    except ValueError:
                        pass

            # Recover any per-edge style overrides that aren't in the
            # default edge style. Currently we round-trip the parallel
            # fan-out keys (entryX/Y, exitX/Y) so a multi-call add_edge
            # sequence keeps an earlier edge's spread intact when a
            # later sibling joins. Add new keys here as the builder
            # learns to emit them.
            edge_style: dict[str, str] = {}
            for k, v in _parse_style_attr(cell.attrib.get("style", "")).items():
                if k in _EDGE_PRESERVED_STYLE_KEYS:
                    edge_style[k] = v

            # Recover explicit routing waypoints from
            # <mxGeometry><Array as="points"><mxPoint .../></Array>.
            # Without this round-trip, the waypoint route an earlier
            # add_edge computed for a cross-container edge would be
            # dropped when the next add_edge re-loads the diagram.
            edge_waypoints: list[tuple[float, float]] = []
            geom = cell.find("mxGeometry")
            if geom is not None:
                arr = geom.find('Array[@as="points"]') or geom.find("Array")
                if arr is not None:
                    for pt in arr.findall("mxPoint"):
                        try:
                            edge_waypoints.append(
                                (float(pt.get("x", "0")), float(pt.get("y", "0")))
                            )
                        except (TypeError, ValueError):
                            pass

            edges.append(
                DiagramEdge(
                    id=cell_id,
                    source_id=cell.attrib.get("source", ""),
                    target_id=cell.attrib.get("target", ""),
                    label=label_clean,
                    step_index=step_idx,
                    style=edge_style,
                    waypoints=edge_waypoints,
                )
            )
        elif cell.attrib.get("vertex") == "1":
            geom = cell.find("mxGeometry")
            style_str = cell.attrib.get("style", "")
            parent_attr = cell.attrib.get("parent", "")

            # Step badge intercept: a vertex cell whose parent is an
            # edge id is the numbered circle the builder emits for
            # DiagramEdge.step_index. Don't promote it to a DiagramNode
            # — it gets re-emitted from the edge's step_index on save.
            if parent_attr in edge_ids:
                try:
                    badge_by_edge_id[parent_attr] = int(
                        cell.attrib.get("value", "").strip()
                    )
                except (TypeError, ValueError):
                    pass  # malformed badge — silently drop
                continue

            # Styles that cannot be round-tripped through SHAPE_STYLES
            # must be preserved verbatim: the GCP image styles we embed
            # AND the swimlane styles with custom colors from add_container
            # (otherwise color_hint is lost on every save/reload cycle).
            preserve_raw = (
                "shape=image" in style_str
                or style_str.startswith("swimlane")
                or ";swimlane;" in style_str
                or style_str.startswith("text;")
            )
            raw = style_str if preserve_raw else None
            # Read parent_id so nested children survive the round-trip.
            # "0" and "1" are mxGraph's root sentinels — treat them as
            # "no parent" since that's how the builder writes top-level
            # nodes (builder.py uses `parent="1"` when parent_id is None).
            parent_id = parent_attr if parent_attr not in ("", "0", "1") else None
            nodes.append(
                DiagramNode(
                    id=cell_id,
                    label=cell.attrib.get("value", ""),
                    shape=_infer_shape(style_str),
                    x=_num(geom, "x", 0),
                    y=_num(geom, "y", 0),
                    width=_num(geom, "width", 120),
                    height=_num(geom, "height", 60),
                    parent_id=parent_id,
                    raw_style=raw,
                )
            )

    # Apply collected step badges to their parent edges. Legacy
    # support: older diagrams stored step_index as a colored-circle
    # child cell. New diagrams encode it directly in the edge label
    # ("N. label" prefix, parsed above). The child-cell read only
    # fires when no label prefix supplied a value.
    if badge_by_edge_id:
        for e in edges:
            if e.step_index is None and e.id in badge_by_edge_id:
                e.step_index = badge_by_edge_id[e.id]

    return Diagram(name=name, nodes=nodes, edges=edges)


def _num(geom: ET.Element | None, attr: str, default: float) -> float:
    if geom is None:
        return default
    try:
        return float(geom.attrib.get(attr, default))
    except (TypeError, ValueError):
        return default


def _infer_shape(style: str) -> str:
    # Swimlane check first — its style starts with "swimlane;..." and
    # must be recognised before generic checks below (which would
    # otherwise misclassify it as "rectangle" and break the column
    # auto-layout in add_container).
    if style.startswith("swimlane") or ";swimlane;" in style:
        return "swimlane"
    if "shape=cylinder" in style:
        return "cylinder"
    if "shape=cloud" in style:
        return "cloud"
    if "umlActor" in style:
        return "actor"
    if "shape=hexagon" in style:
        return "hexagon"
    if "shape=process" in style:
        return "process"
    if "shape=document" in style:
        return "document"
    if "shape=delay" in style:
        return "queue"
    if "ellipse" in style:
        return "ellipse"
    if "rounded=1" in style:
        return "rounded"
    if "dashed=1" in style and "fillColor=none" in style:
        return "container"
    return "rectangle"
