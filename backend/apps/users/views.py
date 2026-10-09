"""Authentication endpoints.

Strategy: short-lived JWT access token returned in the JSON body and held only in browser
memory (never localStorage), plus a rotating refresh token in an httpOnly, SameSite=Strict
cookie scoped to /api/v1/auth/. XSS cannot read the refresh token, and CSRF cannot use it
because SameSite=Strict keeps it off cross-site requests.
"""

import logging

from django.conf import settings
from django.contrib.auth import authenticate
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import LoginSerializer, TokenResponseSerializer, UserSerializer

logger = logging.getLogger("finpilot.auth")


class LoginThrottle(AnonRateThrottle):
    scope = "login"


def _token_response(user: User, refresh: RefreshToken, http_status=status.HTTP_200_OK):
    access = refresh.access_token
    body = {
        "access": str(access),
        "access_expires_in": int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        "user": UserSerializer(user).data,
    }
    response = Response(body, status=http_status)
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        str(refresh),
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=settings.REFRESH_COOKIE_PATH,
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )
    return response


def _refresh_for(user: User) -> RefreshToken:
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    return refresh


class LoginView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: TokenResponseSerializer,
            401: OpenApiResponse(description="Bad credentials"),
        },
        tags=["auth"],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request, **serializer.validated_data)
        if user is None or not user.is_active:
            logger.warning(
                "login_failed", extra={"username": serializer.validated_data["username"]}
            )
            return Response(
                {
                    "error": {
                        "code": "invalid_credentials",
                        "message": "Invalid username or password.",
                    }
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
        logger.info("login_succeeded", extra={"user_id": user.pk, "role": user.role})
        return _token_response(user, _refresh_for(user))


class RefreshView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={200: TokenResponseSerializer}, tags=["auth"])
    def post(self, request):
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not raw:
            return Response(
                {"error": {"code": "not_authenticated", "message": "No active session."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            old = RefreshToken(raw)
            user = User.objects.get(pk=old["user_id"], is_active=True)
        except (TokenError, User.DoesNotExist, KeyError):
            response = Response(
                {"error": {"code": "session_expired", "message": "Session expired."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            response.delete_cookie(settings.REFRESH_COOKIE_NAME, path=settings.REFRESH_COOKIE_PATH)
            return response
        return _token_response(user, _refresh_for(user))


class LogoutView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={204: None}, tags=["auth"])
    def post(self, request):
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(settings.REFRESH_COOKIE_NAME, path=settings.REFRESH_COOKIE_PATH)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserSerializer, tags=["auth"])
    def get(self, request):
        return Response(UserSerializer(request.user).data)
