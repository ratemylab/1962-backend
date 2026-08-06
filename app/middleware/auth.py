from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


PUBLIC_PATHS = {"/health", "/docs", "/openapi.json"}


class AuthMiddleware(BaseHTTPMiddleware):
    """Lightweight request context middleware.

    Authentication is enforced per endpoint by the get_current_client (static
    client token) and get_current_admin (admin JWT) dependencies rather than
    globally at middleware level, so docs, health and login stay public.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        request_id = request.headers.get("X-Request-Id")
        if request_id:
            request.state.request_id = request_id

        response = await call_next(request)
        if request.url.path not in PUBLIC_PATHS and request_id:
            response.headers["X-Request-Id"] = request_id
        return response
