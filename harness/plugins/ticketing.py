"""Ticketing interface and the in-memory plugin (development and tests).

Creating a ticket changes something outside the application, so by harness rule it is a human
action: expose it through an endpoint guarded by a permission (it is then audited like every
call). Do not give it to an agent as a tool.
"""
from __future__ import annotations

import itertools
from typing import Literal, Protocol

from pydantic import BaseModel

from harness.plugins import create, register


class TicketRequest(BaseModel):
    title: str
    description: str
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    requested_by: str
    external_ref: str | None = None      # your record's id, so the ticket can be traced back


class Ticket(BaseModel):
    id: str
    number: str
    status: str
    url: str | None = None


class TicketingError(RuntimeError):
    pass


class TicketingProvider(Protocol):
    def create(self, request: TicketRequest) -> Ticket: ...
    def get(self, ticket_id: str) -> Ticket | None: ...


class MemoryTicketing:
    def __init__(self):
        self.tickets: dict[str, Ticket] = {}
        self.requests: list[TicketRequest] = []
        self._ids = itertools.count(1)

    def create(self, request: TicketRequest) -> Ticket:
        n = next(self._ids)
        ticket = Ticket(id=f"mem-{n}", number=f"TKT{n:07d}", status="new")
        self.tickets[ticket.id] = ticket
        self.requests.append(request)
        return ticket

    def get(self, ticket_id: str) -> Ticket | None:
        return self.tickets.get(ticket_id)


@register("ticketing", "memory")
def _memory(settings) -> MemoryTicketing:
    return MemoryTicketing()


def ticketing_for(settings) -> TicketingProvider | None:
    if settings.ticketing_provider == "none":
        return None
    return create("ticketing", settings.ticketing_provider, settings)
