"""DRF exception handler that gives every error a consistent shape.

Every error response from the API looks like:
    {"error": "<code>", "detail": <message or dict>}
"""

from django.core.exceptions import RequestDataTooBig
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler


# Map DRF / Django exceptions to our consistent shape.
def custom_exception_handler(exc, context):
    # Local import to avoid circulars at startup.
    from kyc.state_machine import IllegalTransition

    if isinstance(exc, IllegalTransition):
        return Response(
            {"error": "illegal_transition", "detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, RequestDataTooBig):
        return Response(
            {"error": "validation", "detail": "Upload too large (max 5 MB)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, ValidationError):
        return Response(
            {"error": "validation", "detail": exc.detail},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, NotFound):
        return Response(
            {"error": "not_found", "detail": str(exc.detail)},
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, PermissionDenied):
        return Response(
            {"error": "forbidden", "detail": str(exc.detail)},
            status=status.HTTP_403_FORBIDDEN,
        )

    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        return Response(
            {"error": "unauthenticated", "detail": str(exc.detail)},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Fallback: let DRF build the default response then wrap it.
    response = exception_handler(exc, context)
    if response is not None:
        original = response.data
        response.data = {"error": "error", "detail": original}
    return response
