"""Rate limiting for auth and QR scan endpoints."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import get_settings

settings = get_settings()


def client_ip_key(request: Request) -> str:
    """Resolve the real client IP for rate limiting.

    Directly-exposed (trusted_proxy_count == 0): use the socket peer address so
    a spoofed X-Forwarded-For cannot bypass the limit.

    Behind N trusted proxies: take the entry that sits N positions from the
    right of X-Forwarded-For — the value appended by the outermost trusted
    proxy — which a client cannot forge past that proxy. Falls back to the peer
    address if the header is missing or too short.
    """
    n = settings.trusted_proxy_count
    if n <= 0:
        return get_remote_address(request)

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= n:
            return parts[-n]
    return get_remote_address(request)


limiter = Limiter(key_func=client_ip_key, default_limits=[])
