import logging
import re
import time
import uuid

from .logging import request_id_var

logger = logging.getLogger("finpilot.access")
_VALID_ID = re.compile(r"^[A-Za-z0-9\-]{8,64}$")


class RequestIdMiddleware:
    """Accepts a well-formed inbound X-Request-ID or mints one, and echoes it back."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        inbound = request.headers.get("X-Request-ID", "")
        request_id = inbound if _VALID_ID.match(inbound) else uuid.uuid4().hex
        request.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response["X-Request-ID"] = request_id
        return response


class AccessLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.perf_counter()
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            user = getattr(request, "user", None)
            logger.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    "user_id": getattr(user, "pk", None),
                },
            )
        return response
