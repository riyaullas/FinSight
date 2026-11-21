"""Security middleware: CSRF double-submit validation and security response headers."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.api.deps import CSRF_COOKIE, CSRF_HEADER
from app.core.security import constant_time_equals

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Server-to-server endpoints authenticated by signature instead of cookies (Phase 2 webhooks).
CSRF_EXEMPT_PREFIXES = ("/api/webhooks/",)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in SAFE_METHODS and not request.url.path.startswith(CSRF_EXEMPT_PREFIXES):
            cookie = request.cookies.get(CSRF_COOKIE)
            header = request.headers.get(CSRF_HEADER)
            if not cookie or not header or not constant_time_equals(cookie, header):
                return JSONResponse({"detail": "CSRF validation failed"}, status_code=403)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        h.setdefault("Cache-Control", "no-store")
        if request.url.path.startswith("/api/docs"):
            # Swagger UI loads its own assets; keep a policy that still blocks framing.
            h.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
        else:
            h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        if request.url.scheme == "https":
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
