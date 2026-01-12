"""
FastAPI middleware for logging and request tracking.

Implements request ID tracking and timing middleware.
"""

import logging
import time
import uuid
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Context variable for request ID (available across async calls)
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

logger = logging.getLogger(__name__)


def get_request_id() -> str:
    """Get current request ID from context."""
    return request_id_ctx.get()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging requests and tracking timing.

    Features:
    - Generates unique request ID for each request
    - Logs request start and completion
    - Tracks response time
    - Adds X-Request-ID header to response
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with logging and timing."""
        # Generate unique request ID
        req_id = str(uuid.uuid4())[:8]  # Short ID for readability
        request_id_ctx.set(req_id)

        # Log request start
        logger.info(
            f"[{req_id}] {request.method} {request.url.path}",
            extra={
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params),
            },
        )

        # Track timing
        start_time = time.time()

        try:
            response = await call_next(request)
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"[{req_id}] Request failed after {elapsed:.2f}s: {e}",
                extra={"request_id": req_id, "elapsed_ms": elapsed * 1000},
                exc_info=True,
            )
            raise

        elapsed = time.time() - start_time

        # Log response
        logger.info(
            f"[{req_id}] {response.status_code} in {elapsed:.2f}s",
            extra={
                "request_id": req_id,
                "status_code": response.status_code,
                "elapsed_ms": elapsed * 1000,
            },
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = req_id

        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for adding response timing header.

    Adds X-Response-Time header with request processing time.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and add timing header."""
        start_time = time.time()
        response = await call_next(request)
        elapsed = time.time() - start_time

        response.headers["X-Response-Time"] = f"{elapsed:.3f}s"
        return response
