from __future__ import annotations

from pydantic import BaseModel


class Page[T](BaseModel):
    """Standard paginated response for every list endpoint."""

    items: list[T]
    total: int
    limit: int
    offset: int
