"""Natural-sort key for Jira-style filenames.

A plain ``sorted()`` puts ``PROJ-10`` before ``PROJ-2`` because it compares
codepoints. ``natural_key`` splits each name into runs of digits and
non-digits, casts the digit runs to int, and returns a tuple — so the
comparison happens numerically on the digit runs and case-insensitively on
the rest.
"""

from __future__ import annotations

import re

_SPLIT = re.compile(r"(\d+)")


def natural_key(name: str) -> tuple[object, ...]:
    parts = _SPLIT.split(name)
    return tuple(int(p) if p.isdigit() else p.lower() for p in parts)
