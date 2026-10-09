import logging

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger("finpilot.health")

_health_schema = inline_serializer(
    "Health",
    {
        "status": serializers.CharField(),
        "checks": serializers.DictField(child=serializers.CharField()),
    },
)


class LivenessView(APIView):
    """Process is up. Never touches dependencies so it cannot cascade failures."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(responses=_health_schema, tags=["health"])
    def get(self, request):
        return Response({"status": "ok", "checks": {"process": "ok"}})


class ReadinessView(APIView):
    """Ready to serve traffic: database reachable and no unapplied migrations."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(responses={200: _health_schema, 503: _health_schema}, tags=["health"])
    def get(self, request):
        checks = {}
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            checks["database"] = "ok"
            executor = MigrationExecutor(connection)
            pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
            checks["migrations"] = "ok" if not pending else f"{len(pending)} pending"
        except Exception:  # noqa: BLE001 - report, never leak connection details
            logger.exception("readiness_check_failed")
            checks["database"] = "unavailable"
        healthy = all(value == "ok" for value in checks.values())
        return Response(
            {"status": "ok" if healthy else "degraded", "checks": checks},
            status=200 if healthy else 503,
        )
