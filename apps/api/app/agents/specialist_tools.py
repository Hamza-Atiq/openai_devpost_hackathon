from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def require_allowed_tools(tools: Iterable[Any], allowed_names: frozenset[str]) -> list[Any]:
    selected = list(tools)
    disallowed = sorted(
        tool.name for tool in selected if getattr(tool, "name", None) not in allowed_names
    )
    if disallowed:
        raise ValueError(f"tools not allowed for this specialist: {', '.join(disallowed)}")
    return selected
