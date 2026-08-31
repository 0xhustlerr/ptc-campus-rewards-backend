"""Request logging and unhandled-error middleware."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.exceptions import ErrorResponse

logger = logging.getLogger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.perf_counter()

        logger.info(
            "request_start method=%s path=%s request_id=%s",
            request.method,
            request.url.path,
            request_id,
        )

        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "request_end method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response


class UnhandledErrorMiddleware(BaseHTTPMiddleware):
    """Turn an unhandled exception into a JSON 500 from inside the CORS layer.

    Starlette's ServerErrorMiddleware sits outside CORSMiddleware, so the 500 it
    emits carries no CORS headers. A browser then blocks the response and the
    frontend reports a connection failure instead of the actual API error, which
    hides the real problem from admins and from us.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except Exception:
            logger.exception("Unhandled error on %s %s", request.method, request.url.path)
            body = ErrorResponse(detail="Internal server error", code="internal_error")
            return JSONResponse(status_code=500, content=body.model_dump())
