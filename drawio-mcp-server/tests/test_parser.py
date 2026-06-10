"""Placeholder test scaffolding. Run with `pytest`.

Suggested coverage:
- parse_drawio + build_drawio roundtrip
- parse_drawio rejects compressed mxfile with the expected error
- DiagramStore rejects path traversal (e.g. name='../etc/passwd')
- StoryStore lists only .txt/.md/.json files
- add_node auto-places to the right of the rightmost existing node
- remove_element on a node also removes its incident edges
"""

from __future__ import annotations


def test_placeholder() -> None:
    assert True
