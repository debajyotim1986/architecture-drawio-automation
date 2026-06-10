"""Compact, label-oriented view of a Diagram.

This is what Copilot consumes most often — it is small, readable, and
avoids spending tokens on geometry/style noise.
"""

from __future__ import annotations

from ..types import Diagram, DiagramSummary, DiagramSummaryEdge, DiagramSummaryNode


def summarize(d: Diagram) -> DiagramSummary:
    label_by_id = {n.id: n.label for n in d.nodes}
    return DiagramSummary(
        name=d.name,
        node_count=len(d.nodes),
        edge_count=len(d.edges),
        nodes=[DiagramSummaryNode(id=n.id, label=n.label, shape=n.shape) for n in d.nodes],
        edges=[
            DiagramSummaryEdge(
                id=e.id,
                **{
                    "from": label_by_id.get(e.source_id, e.source_id),
                    "to": label_by_id.get(e.target_id, e.target_id),
                },
                relation=e.label,
            )
            for e in d.edges
        ],
    )
