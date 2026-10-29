import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from auth import BearerTokenMiddleware, validate_auth_configuration


def create_test_app():
    async def health(_request):
        return JSONResponse({"status": "HEALTHY"})

    async def private(_request):
        return JSONResponse({"status": "OK"})

    app = Starlette(
        routes=[
            Route("/health", health),
            Route("/private", private),
        ]
    )
    app.add_middleware(BearerTokenMiddleware, exempt_paths={"/health"})
    return app


def test_authentication_is_optional_for_local_development(monkeypatch):
    monkeypatch.delenv("FAIA_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("FAIA_REQUIRE_AUTH", raising=False)

    with TestClient(create_test_app()) as client:
        assert client.get("/private").status_code == 200


def test_authentication_protects_private_routes_and_preserves_health(monkeypatch):
    token = "test-token-with-more-than-thirty-two-characters"
    monkeypatch.setenv("FAIA_AUTH_TOKEN", token)
    monkeypatch.setenv("FAIA_REQUIRE_AUTH", "true")

    with TestClient(create_test_app()) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/private").status_code == 401
        assert client.options("/private").status_code != 401
        assert client.get(
            "/private",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code == 200


def test_authentication_rejects_missing_or_weak_required_secret(monkeypatch):
    monkeypatch.setenv("FAIA_REQUIRE_AUTH", "true")
    monkeypatch.delenv("FAIA_AUTH_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="FAIA_AUTH_TOKEN is required"):
        validate_auth_configuration()

    monkeypatch.setenv("FAIA_AUTH_TOKEN", "too-short")
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        validate_auth_configuration()


def test_authentication_rejects_invalid_required_setting(monkeypatch):
    monkeypatch.setenv("FAIA_REQUIRE_AUTH", "sometimes")
    with pytest.raises(RuntimeError, match="must be set to true or false"):
        validate_auth_configuration()
