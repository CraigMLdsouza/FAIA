"""Shared bearer-token authentication for remotely hosted HTTP services."""

from __future__ import annotations

import hmac
import os
from collections.abc import Iterable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


_MIN_TOKEN_LENGTH = 32


def _auth_settings() -> tuple[str | None, bool]:
    token = os.environ.get("FAIA_AUTH_TOKEN")
    required_value = os.environ.get("FAIA_REQUIRE_AUTH", "false").strip().lower()
    if required_value not in {"true", "false", "1", "0", "yes", "no"}:
        raise RuntimeError("FAIA_REQUIRE_AUTH must be set to true or false.")

    required = required_value in {"true", "1", "yes"}
    if required and not token:
        raise RuntimeError("FAIA_AUTH_TOKEN is required when FAIA_REQUIRE_AUTH is enabled.")
    if token and len(token) < _MIN_TOKEN_LENGTH:
        raise RuntimeError(
            f"FAIA_AUTH_TOKEN must be at least {_MIN_TOKEN_LENGTH} characters long."
        )
    return token, required


def validate_auth_configuration() -> None:
    """Fail fast when authentication is required but missing or weak."""
    _auth_settings()


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Protect HTTP routes with an optional shared bearer token."""

    def __init__(
        self,
        app: Any,
        *,
        exempt_paths: Iterable[str] = (),
    ) -> None:
        super().__init__(app)
        self.token, self.required = _auth_settings()
        self.exempt_paths = frozenset(exempt_paths)

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if request.url.path in self.exempt_paths or request.method == "OPTIONS":
            return await call_next(request)

        if self.token is None and not self.required:
            return await call_next(request)

        authorization = request.headers.get("authorization", "")
        provided_token = (
            authorization[len("Bearer "):]
            if authorization.startswith("Bearer ")
            else ""
        )
        if self.token is None or not hmac.compare_digest(provided_token, self.token):
            return JSONResponse(
                {"detail": "A valid bearer token is required."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)
