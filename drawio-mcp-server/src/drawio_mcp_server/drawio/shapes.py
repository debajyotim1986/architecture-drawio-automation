"""Maps intent-level NodeShape names to draw.io style strings.

Keep this table small and obvious — the LLM picks shapes by name, the
server translates to mxGraph here.
"""

from __future__ import annotations

SHAPE_STYLES: dict[str, str] = {
    "rectangle": "rounded=0;whiteSpace=wrap;html=1;",
    "rounded": "rounded=1;whiteSpace=wrap;html=1;",
    "ellipse": "ellipse;whiteSpace=wrap;html=1;",
    "cylinder": "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;",
    "cloud": "ellipse;shape=cloud;whiteSpace=wrap;html=1;",
    "actor": "shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;",
    "hexagon": "shape=hexagon;perimeter=hexagonPerimeter2;whiteSpace=wrap;html=1;",
    "process": "shape=process;whiteSpace=wrap;html=1;backgroundOutline=1;",
    "document": "shape=document;whiteSpace=wrap;html=1;boundedLbl=1;",
    "queue": "shape=delay;whiteSpace=wrap;html=1;",
    "container": "rounded=0;whiteSpace=wrap;html=1;fillColor=none;dashed=1;verticalAlign=top;",
    # Swimlane: labeled box with a colored header strip and a white body.
    # Children placed with `parent_id=<swimlane>` render INSIDE this box at
    # coordinates relative to its top-left. The default colors below are
    # overridden per-instance by add_container's color_hint palette.
    "swimlane": (
        "swimlane;html=1;rounded=0;startSize=30;fontSize=14;fontStyle=1;"
        "swimlaneFillColor=#ffffff;fillColor=#dae8fc;strokeColor=#6c8ebf;"
        "verticalAlign=top;align=center;"
    ),
}

# Edge style — every one of these knobs is load-bearing for arrowhead
# rendering and routing quality across drawio variants (desktop, web,
# VS Code extension):
#   endArrow=classic   → which arrowhead shape to draw at the target.
#   endFill=1          → fill the arrowhead solid; SOME renderers leave
#                        the arrowhead as a hairline outline (effectively
#                        invisible) when this is omitted, even though
#                        endArrow=classic is set. Without this attribute
#                        we saw "many connectors with no arrow".
#   endSize=12         → arrowhead size in px; pin it so it stays
#                        visible against the orthogonal-router thickness.
#   startArrow=none    → explicit "no arrow at the source end"; without
#                        this some drawio versions auto-draw an arrow at
#                        the source too, making it look bidirectional.
#   startFill=0        → belt & suspenders for the same.
#   strokeWidth=1.5    → thicker line so the arrow reads at a glance.
#   jettySize=22       → MINIMUM perpendicular distance the edge must
#                        extend from each endpoint before bending. This
#                        is what stops the orthogonal router from
#                        drawing a line directly across a neighboring
#                        node — the edge MUST get out of the node's
#                        bounding box (and a few pixels past it) before
#                        making its first turn. 22 is comfortably more
#                        than the 16-px padding inside our swimlanes,
#                        so the bend always happens in the
#                        between-swimlane gap rather than over an icon.
#   rounded=1          → soften the bend corners so the 90° turns look
#                        like flowing arcs rather than sharp squares.
#                        Better signal-to-noise than rounded=0 when
#                        many edges share the diagram.
# verticalAlign=bottom + align=center: the label's bottom-centre anchors
# at the offset point above the segment, so the text floats clearly
# *above* the arrow instead of straddling it.
# fontColor + fontStyle: connector labels render in distinct Google-blue
# bold so they pop visually against the black icon-name labels below
# each GCP shape — no more "which label belongs to what?" ambiguity.
# fontSize=11 keeps them compact (smaller than the 12-13px icon labels)
# so the connector label reads as metadata, not as primary content.
# labelBackgroundColor gives the label a white pill so it stays readable
# when an orthogonal edge unavoidably crosses another edge or node corner.
DEFAULT_EDGE_STYLE = (
    "endArrow=classic;endFill=1;endSize=12;startArrow=none;startFill=0;"
    "html=1;rounded=1;edgeStyle=orthogonalEdgeStyle;jettySize=22;"
    "strokeWidth=1.5;"
    "align=center;verticalAlign=bottom;"
    "fontColor=#0B57D0;fontStyle=1;fontSize=11;"
    "labelBackgroundColor=#ffffff;"
)

# Style keys that must be set + non-"none" for an edge to render its
# directional arrowhead. Used by both the builder (default) and the
# verifier (check). Keep this list in sync with DEFAULT_EDGE_STYLE
# above — any new "no arrow rendered" bug should add the missing key
# here so the verifier catches it before the diagram is delivered.
REQUIRED_ARROW_KEYS: tuple[tuple[str, str], ...] = (
    ("endArrow", "none"),  # (key, forbidden_value)
    ("endFill", "0"),
)

DEFAULT_SIZE: dict[str, tuple[float, float]] = {
    "rectangle": (160, 60),
    "rounded": (160, 60),
    "ellipse": (140, 60),
    "cylinder": (80, 80),
    "cloud": (160, 100),
    "actor": (40, 60),
    "hexagon": (140, 70),
    "process": (160, 60),
    "document": (140, 70),
    "queue": (120, 60),
    "container": (320, 200),
    # Tall columns sized for ~5 stacked 64px GCP-icon children with
    # generous vertical gaps between rows so the orthogonal edge
    # router has clear horizontal lanes BETWEEN icons. Height kept
    # at 1080 to comfortably hold 5 children at the 200-px stride
    # (was 820 at the previous 150-px stride).
    "swimlane": (240, 1080),
}


# Style for the numbered "step" badge drawn on each edge midpoint when
# DiagramEdge.step_index is set. White bold digit on a colored circle.
# The `relative=1` + offset geometry sits the badge ON the edge, not
# floating beside it.
STEP_BADGE_STYLE_FMT = (
    "ellipse;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
    "fontColor=#ffffff;fontSize=12;fontStyle=1;align=center;verticalAlign=middle;"
    "labelBackgroundColor=none;"
)
STEP_BADGE_SIZE = (24.0, 24.0)


# 10-color cycle for the numbered edge badges. Picked for high contrast
# so consecutive numbers stay visually distinct on a busy diagram. After
# step 10 the palette wraps — but for >10 steps the visual ordering is
# usually clear enough from the number itself.
EDGE_NUMBER_COLORS: list[tuple[str, str]] = [
    ("#e6194b", "#9c1530"),  # 1 red
    ("#f58231", "#ad5a23"),  # 2 orange
    ("#ffd700", "#b29800"),  # 3 yellow (deeper than #ffe119 for white-text contrast)
    ("#3cb44b", "#2a7f35"),  # 4 green
    ("#4363d8", "#2f4699"),  # 5 blue
    ("#911eb4", "#671580"),  # 6 purple
    ("#f032e6", "#aa23a0"),  # 7 pink
    ("#9a6324", "#6c4419"),  # 8 brown
    ("#469990", "#316b65"),  # 9 teal
    ("#1f1f1f", "#000000"),  # 10 near-black
]


# Title banner style: transparent rectangle, no border, bold large text.
# Used by the add_title tool to put a "deck-quality" header above the
# swimlanes. Two sizes — TITLE for the main line, SUBTITLE for an
# optional second line (Jira key + tagline).
TITLE_STYLE = (
    "text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;"
    "fontSize=22;fontStyle=1;fontColor=#222222;whiteSpace=wrap;"
)
SUBTITLE_STYLE = (
    "text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;"
    "fontSize=13;fontStyle=0;fontColor=#666666;whiteSpace=wrap;"
)


# Color palette for swimlane containers, keyed by a short semantic hint
# the LLM picks per layer. Each value is (header_fill, border_stroke).
# Kept small and distinct so a 5-7 column diagram reads at a glance.
SWIMLANE_COLORS: dict[str, tuple[str, str]] = {
    "ingestion":     ("#dae8fc", "#6c8ebf"),  # light blue
    "processing":    ("#fff2cc", "#d6b656"),  # light yellow
    "staging":       ("#d5e8d4", "#82b366"),  # light green
    "curation":      ("#e1d5e7", "#9673a6"),  # light purple
    "serving":       ("#ffe6cc", "#d79b00"),  # light orange
    "observability": ("#f5f5f5", "#666666"),  # light gray
    "external":      ("#f8cecc", "#b85450"),  # light red — for non-GCP / on-prem zones
    "security":      ("#fad9d5", "#ae4132"),  # deeper red — for IAM / Secret Manager
    "default":       ("#f5f5f5", "#666666"),  # neutral gray
}
