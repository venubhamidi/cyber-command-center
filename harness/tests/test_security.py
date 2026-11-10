"""Authentication plugins and RBAC."""
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from harness.app import UnsafeConfiguration
from harness.plugins.auth_oidc import OidcJwtAuth
from harness.tests.conftest import OUTSIDER, READER

ISSUER, AUDIENCE = "https://idp.example.com/", "api://test-app"


def test_static_tokens_401_403_200(make_app):
    c = TestClient(make_app())
    assert c.get("/api/v1/things").status_code == 401
    assert c.get("/api/v1/things", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert c.get("/api/v1/things", headers=OUTSIDER).status_code == 403
    assert c.get("/api/v1/things", headers=READER).json()["total"] == 3


def test_static_tokens_are_refused_in_production(make_app):
    with pytest.raises(UnsafeConfiguration):
        make_app(environment="prod")


# ---- OIDC single sign-on ----
@pytest.fixture(scope="module")
def idp():
    """A stand-in identity provider: a signing key and its published key set (JWKS)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="key-1", use="sig", alg="RS256")
    return key, json.dumps({"keys": [jwk]})


def token(key, *, kid="key-1", alg="RS256", **claims) -> str:
    body = {"iss": ISSUER, "aud": AUDIENCE, "sub": "alice@example.com", "roles": ["App.Readers"],
            "exp": int(time.time()) + 300}
    body.update(claims)
    return jwt.encode({k: v for k, v in body.items() if v is not None}, key, algorithm=alg, headers={"kid": kid})


@pytest.fixture
def sso_client(make_app, idp):
    app = make_app(auth_provider="oidc", oidc_issuer=ISSUER, oidc_audience=AUDIENCE, oidc_jwks_json=idp[1],
                   oidc_role_map={"App.Readers": "reader", "App.Admins": "admin"})
    return TestClient(app)


def bearer(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def test_oidc_valid_token_is_accepted_and_roles_are_mapped(sso_client, idp):
    r = sso_client.get("/api/v1/whoami", headers=bearer(token(idp[0])))
    assert r.status_code == 200 and r.json() == {"subject": "alice@example.com", "roles": ["reader"]}


def test_oidc_also_works_in_production_mode(make_app, idp):
    app = make_app(environment="prod", auth_provider="oidc", oidc_issuer=ISSUER, oidc_audience=AUDIENCE,
                   oidc_jwks_json=idp[1], oidc_role_map={"App.Readers": "reader"})
    assert TestClient(app).get("/api/v1/things", headers=bearer(token(idp[0]))).status_code == 200


@pytest.mark.parametrize("claims", [
    {"exp": int(time.time()) - 10},              # expired
    {"aud": "api://another-app"},                # issued for a different application
    {"iss": "https://evil.example.com/"},        # issued by someone else
    {"sub": None},                               # no subject
    {"exp": None},                               # never expires
])
def test_oidc_rejects_bad_claims(sso_client, idp, claims):
    assert sso_client.get("/api/v1/things", headers=bearer(token(idp[0], **claims))).status_code == 401


def test_oidc_rejects_token_signed_by_another_key(sso_client):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert sso_client.get("/api/v1/things", headers=bearer(token(other))).status_code == 401
    assert sso_client.get("/api/v1/things", headers=bearer(token(other, kid="unknown"))).status_code == 401


def test_oidc_rejects_unsigned_and_shared_secret_tokens(sso_client):
    body = {"iss": ISSUER, "aud": AUDIENCE, "sub": "mallory", "roles": ["App.Admins"], "exp": int(time.time()) + 300}
    unsigned = jwt.encode(body, None, algorithm="none", headers={"kid": "key-1"})
    shared = jwt.encode(body, "a-guessable-secret-of-sufficient-length!", algorithm="HS256", headers={"kid": "key-1"})
    assert sso_client.get("/api/v1/things", headers=bearer(unsigned)).status_code == 401
    assert sso_client.get("/api/v1/things", headers=bearer(shared)).status_code == 401
    assert sso_client.get("/api/v1/things", headers=bearer("not-a-jwt")).status_code == 401


def test_oidc_unmapped_roles_grant_nothing(sso_client, idp):
    r = sso_client.get("/api/v1/things", headers=bearer(token(idp[0], roles=["Some.Other.Group"])))
    assert r.status_code == 403


def test_oidc_configuration_must_be_complete_and_asymmetric(idp):
    common = dict(subject_claim="sub", roles_claim="roles", role_map={})
    with pytest.raises(ValueError):
        OidcJwtAuth(issuer="", audience=AUDIENCE, algorithms=["RS256"], jwks_json=idp[1], **common)
    with pytest.raises(ValueError):
        OidcJwtAuth(issuer=ISSUER, audience=AUDIENCE, algorithms=["RS256"], **common)   # no keys
    for bad in (["HS256"], ["none"], []):
        with pytest.raises(ValueError):
            OidcJwtAuth(issuer=ISSUER, audience=AUDIENCE, algorithms=bad, jwks_json=idp[1], **common)
