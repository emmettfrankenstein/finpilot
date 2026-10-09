"""Uniform error envelope: {"error": {"code", "message", "details", "request_id"}}.

Unhandled exceptions are logged with their stack trace server-side and returned to the
client as a generic 500 without internal details.
"""

import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .logging import request_id_var

logger = logging.getLogger("finpilot.errors")


class ConflictError(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "conflict"
    default_detail = "The request conflicts with the current state of the resource."


def _envelope(code: str, message: str, details=None, http_status: int = 400) -> Response:
    body = {"error": {"code": code, "message": message, "request_id": request_id_var.get()}}
    if details is not None:
        body["error"]["details"] = details
    return Response(body, status=http_status)


def api_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None:
        logger.exception("unhandled_api_error", extra={"view": type(context.get("view")).__name__})
        return _envelope("server_error", "An unexpected error occurred.", http_status=500)

    if isinstance(exc, exceptions.ValidationError):
        return _envelope(
            "validation_error",
            "The request contains invalid fields.",
            details=response.data,
            http_status=response.status_code,
        )

    codes = exc.get_codes() if isinstance(exc, exceptions.APIException) else None
    code = codes if isinstance(codes, str) else getattr(exc, "default_code", "error")
    detail = exc.detail if isinstance(exc, exceptions.APIException) else response.data
    if response.status_code >= 500:
        logger.error("api_error", extra={"status": response.status_code, "code": code})
    new = _envelope(str(code), str(detail), http_status=response.status_code)
    for header in ("WWW-Authenticate", "Retry-After"):
        if header in response:
            new[header] = response[header]
    return new
