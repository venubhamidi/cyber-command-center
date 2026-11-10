"""Audit trail: every API call and agent tool call is recorded, including denied ones.

Records are hash-chained (tamper-evident): each row stores the hash of the previous row and a
hash of its own content. verify_audit_chain() recomputes the chain and reports the first row
that does not match. This detects edits and deletions inside the log. It does not stop someone
who can rewrite the whole table; for that, ship the latest hash to a system they cannot reach.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from harness.db import get_conn

_CHAIN_LOCK = 7461002


def _row_hash(prev_hash: str | None, occurred_at: datetime, principal: str, role: str | None, action: str,
              resource: str | None, status_code: int | None, request_id: str | None, detail: Any) -> str:
    payload = json.dumps([prev_hash, occurred_at.astimezone(UTC).isoformat(), principal, role, action,
                          resource, status_code, request_id, detail], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def append_audit(conn, *, principal: str, role: str | None, action: str, resource: str | None = None,
                 status_code: int | None = None, request_id: str | None = None,
                 detail: dict | None = None) -> None:
    """Append one record inside the caller's transaction. Appends are serialized by a lock."""
    conn.execute("SELECT pg_advisory_xact_lock(%s)", (_CHAIN_LOCK,))
    last = conn.execute("SELECT row_hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    prev_hash = last["row_hash"] if last else None
    occurred_at = datetime.now(UTC)
    detail = json.loads(json.dumps(detail, default=str)) if detail is not None else None
    row_hash = _row_hash(prev_hash, occurred_at, principal, role, action, resource, status_code, request_id, detail)
    conn.execute(
        """INSERT INTO audit_log (occurred_at, principal, role, action, resource, status_code, request_id,
                                  detail, prev_hash, row_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (occurred_at, principal, role, action, resource, status_code, request_id,
         json.dumps(detail) if detail is not None else None, prev_hash, row_hash),
    )


def verify_audit_chain(conn) -> tuple[bool, int | None]:
    """Return (True, None) if the log is intact, else (False, id of the first bad row)."""
    prev_hash = None
    for r in conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall():
        expected = _row_hash(r["prev_hash"], r["occurred_at"], r["principal"], r["role"], r["action"],
                             r["resource"], r["status_code"], r["request_id"], r["detail"])
        if r["prev_hash"] != prev_hash or r["row_hash"] != expected:
            return False, r["id"]
        prev_hash = r["row_hash"]
    return True, None


class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, database_url: str):
        super().__init__(app)
        self.database_url = database_url

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            principal = getattr(request.state, "principal", None)
            with get_conn(self.database_url) as conn:
                append_audit(conn,
                             principal=principal.subject if principal else "anonymous",
                             role=principal.role if principal else None,
                             action=f"{request.method} {request.url.path}", resource=request.url.path,
                             status_code=response.status_code, request_id=request_id,
                             detail={"query": dict(request.query_params)} if request.query_params else None)
                conn.commit()
        response.headers["x-request-id"] = request_id
        return response
