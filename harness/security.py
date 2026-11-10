"""Authentication and authorization, domain-neutral.

Who the caller is comes from an "auth" plugin (static dev tokens, OIDC single sign-on, or your own).
What they may do comes from the application's role table. Routes only ever write:

    def endpoint(_: Principal = Depends(require("things:read"))): ...

so changing the identity provider never touches a route.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    """What an auth plugin returns for a valid credential."""

    subject: str
    roles: tuple[str, ...]
    attributes: dict[str, Any] = field(default_factory=dict)   # for attribute-based checks (department, ...)


class AuthProvider(Protocol):
    def authenticate(self, token: str) -> Identity | None:
        """Return the caller's identity, or None if the credential is not valid."""


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: tuple[str, ...]
    permissions: frozenset[str] = field(default_factory=frozenset)
    attributes: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    @property
    def role(self) -> str:
        return ",".join(self.roles)

    def can(self, permission: str) -> bool:
        return "*" in self.permissions or permission in self.permissions


def get_principal(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Principal:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    provider: AuthProvider = request.app.state.auth_provider
    identity = provider.authenticate(creds.credentials)
    if identity is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    role_table: dict[str, set[str]] = request.app.state.role_permissions
    permissions: set[str] = set()
    for role in identity.roles:
        permissions |= role_table.get(role, set())     # roles the application does not know grant nothing
    principal = Principal(identity.subject, identity.roles, frozenset(permissions), identity.attributes)
    request.state.principal = principal                # read by the audit middleware
    return principal


def require(permission: str) -> Callable[..., Principal]:
    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Role '{principal.role}' lacks '{permission}'")
        return principal

    return _dep
