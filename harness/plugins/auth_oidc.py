"""Auth plugin "oidc": single sign-on with any OpenID Connect identity provider
(Microsoft Entra ID, Okta, Keycloak, Ping, Google, ...).

The API receives the access token the identity provider issued (a signed JWT) as the bearer
token and verifies, on every request: signature (against the provider's published keys),
issuer, audience, expiry, and that the algorithm is one we allow. The caller's roles are read
from a claim and translated through APP_OIDC_ROLE_MAP into application roles.

Settings: APP_OIDC_ISSUER, APP_OIDC_AUDIENCE, and either APP_OIDC_JWKS_URL (normal) or
APP_OIDC_JWKS_JSON (air-gapped sites, tests). Optional: APP_OIDC_ROLES_CLAIM (default "roles"),
APP_OIDC_SUBJECT_CLAIM (default "sub"), APP_OIDC_ROLE_MAP, APP_OIDC_ALGORITHMS.

This plugin validates tokens. The browser login redirect that obtains the token is the
front end's job and is not part of the harness yet.
"""
from __future__ import annotations

import json

import jwt

from harness.plugins import register
from harness.security import Identity

# Unsigned ("none") and shared-secret (HS*) tokens are never accepted.

class OidcJwtAuth:
    def __init__(self, *, issuer: str, audience: str, algorithms: list[str], subject_claim: str,
                 roles_claim: str, role_map: dict[str, str], jwks_url: str = "", jwks_json: str = ""):
        if not issuer or not audience:
            raise ValueError("OIDC needs APP_OIDC_ISSUER and APP_OIDC_AUDIENCE")
        if not jwks_url and not jwks_json:
            raise ValueError("OIDC needs APP_OIDC_JWKS_URL or APP_OIDC_JWKS_JSON")
        bad = sorted(a for a in algorithms if a.lower() == "none" or a.upper().startswith("HS"))
        if bad or not algorithms:
            raise ValueError(f"OIDC algorithms must be asymmetric; refused: {bad or 'empty list'}")
        self.issuer, self.audience, self.algorithms = issuer, audience, algorithms
        self.subject_claim, self.roles_claim, self.role_map = subject_claim, roles_claim, role_map
        self._key_set = jwt.PyJWKSet.from_dict(json.loads(jwks_json)) if jwks_json else None
        self._key_client = jwt.PyJWKClient(jwks_url) if jwks_url and not jwks_json else None

    def _signing_key(self, token: str):
        if self._key_client is not None:
            return self._key_client.get_signing_key_from_jwt(token).key
        kid = jwt.get_unverified_header(token).get("kid")
        for key in self._key_set.keys:
            if key.key_id == kid:
                return key.key
        raise jwt.InvalidTokenError("Unknown signing key")

    def authenticate(self, token: str) -> Identity | None:
        try:
            claims = jwt.decode(token, self._signing_key(token), algorithms=self.algorithms,
                                audience=self.audience, issuer=self.issuer,
                                options={"require": ["exp", "iss", "aud", self.subject_claim]})
        except (jwt.PyJWTError, ValueError, KeyError):
            return None     # any failure is "not authenticated"; the reason is never sent to the caller
        raw = claims.get(self.roles_claim, [])
        raw_roles = raw.split() if isinstance(raw, str) else list(raw)
        # Only mapped roles count. With an empty map, IdP role names are used as they are.
        roles = [self.role_map[r] for r in raw_roles if r in self.role_map] if self.role_map else raw_roles
        attributes = {k: v for k, v in claims.items() if k not in ("exp", "iat", "nbf", "iss", "aud")}
        return Identity(subject=str(claims[self.subject_claim]), roles=tuple(dict.fromkeys(roles)), attributes=attributes)


@register("auth", "oidc")
def build(settings) -> OidcJwtAuth:
    return OidcJwtAuth(issuer=settings.oidc_issuer, audience=settings.oidc_audience,
                       algorithms=settings.oidc_algorithms, subject_claim=settings.oidc_subject_claim,
                       roles_claim=settings.oidc_roles_claim, role_map=settings.oidc_role_map,
                       jwks_url=settings.oidc_jwks_url, jwks_json=settings.oidc_jwks_json)
