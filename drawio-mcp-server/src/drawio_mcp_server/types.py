"""Lightweight, intent-level representation of a draw.io diagram.

The on-disk format is mxGraph XML wrapped in a <mxfile> envelope. Copilot
does not work directly with that XML — it works with these models via the
MCP tools, and the parser/builder in drawio/ converts between the two.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

NodeShape = Literal[
    "rectangle",
    "rounded",
    "ellipse",
    "cylinder",      # database
    "cloud",         # external SaaS
    "actor",         # user / persona
    "hexagon",
    "process",
    "document",
    "queue",         # message broker / topic
    "container",     # plain grouping box (dashed border, no header)
    "swimlane",      # labeled layer/zone (header strip + body) — used by add_container
]


class DiagramNode(BaseModel):
    id: str
    label: str
    shape: NodeShape
    x: float = 0
    y: float = 0
    width: float = 160
    height: float = 60
    parent_id: Optional[str] = None
    style: dict[str, str] = Field(default_factory=dict)
    # Set when the node uses a non-stencil style (e.g. an inlined GCP icon).
    # When present the builder emits this verbatim instead of looking up the
    # shape table, which is how GCP icons survive a read/update round-trip.
    raw_style: Optional[str] = None


class DiagramEdge(BaseModel):
    id: str
    source_id: str
    target_id: str
    label: Optional[str] = None
    style: dict[str, str] = Field(default_factory=dict)
    # Optional 1-based sequence number. When set, the builder renders a
    # small colored circle on the edge midpoint with this digit — used
    # to show data-flow ordering on architecture diagrams. add_edge
    # auto-assigns this if the caller doesn't specify a value.
    step_index: Optional[int] = None
    # Explicit routing waypoints in absolute diagram coordinates.
    # When non-empty, the builder emits these as <Array as="points">
    # inside the edge's mxGeometry, forcing drawio's orthogonal
    # router to bend the line through them. Used by add_edge to
    # route cross-container edges through known-empty row gaps so
    # they don't draw over icons in intermediate swimlanes.
    waypoints: list[tuple[float, float]] = Field(default_factory=list)


class Diagram(BaseModel):
    name: str
    nodes: list[DiagramNode] = Field(default_factory=list)
    edges: list[DiagramEdge] = Field(default_factory=list)


class DiagramSummaryNode(BaseModel):
    id: str
    label: str
    shape: NodeShape


class DiagramSummaryEdge(BaseModel):
    id: str
    from_: str = Field(alias="from")
    to: str
    relation: Optional[str] = None

    model_config = {"populate_by_name": True}


class DiagramSummary(BaseModel):
    name: str
    node_count: int
    edge_count: int
    nodes: list[DiagramSummaryNode]
    edges: list[DiagramSummaryEdge]
