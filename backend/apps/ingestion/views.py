import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import ConflictError
from apps.users.permissions import IsAdminRole

from .models import Dataset, ImportBatch, RowOutcome
from .serializers import (
    ImportBatchSerializer,
    ImportResultSerializer,
    ImportUploadSerializer,
    RowFilterSerializer,
    StagedRowSerializer,
)
from .services import DuplicateFileError, InvalidFileError, run_import

logger = logging.getLogger("finpilot.import")

IMPORT_EXAMPLE = {
    "id": 8,
    "dataset": "transactions",
    "source": "api",
    "file_name": "transactions.csv",
    "file_sha256": "9f2c...e1",
    "status": "COMPLETED",
    "total_rows": 4554,
    "inserted_rows": 4550,
    "duplicate_rows": 1,
    "rejected_rows": 3,
    "warning_rows": 1070,
    "error_message": "",
    "created_by": "admin",
    "created_at": "2026-10-09T10:00:00+05:30",
    "finished_at": "2026-10-09T10:00:02+05:30",
    "rejected": [
        {
            "row_number": 4552,
            "record_key": "T0004551",
            "outcome": "REJECTED",
            "errors": ["instrument_id: 'I9999' does not exist"],
            "warnings": [],
            "raw": {"transaction_id": "T0004551", "instrument_id": "I9999", "...": "..."},
        }
    ],
}


class ImportUploadView(APIView):
    permission_classes = [IsAdminRole]
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=["admin-imports"],
        request={"multipart/form-data": ImportUploadSerializer},
        responses={
            201: ImportResultSerializer,
            400: OpenApiResponse(description="Unreadable file, missing columns or no rows"),
            403: OpenApiResponse(description="Caller is not ADMIN"),
            409: OpenApiResponse(description="This exact file was already imported"),
        },
        examples=[
            OpenApiExample(
                "Transactions import",
                value=IMPORT_EXAMPLE,
                response_only=True,
                status_codes=["201"],
            )
        ],
    )
    def post(self, request, dataset: str):
        """Validate a CSV, stage every row, merge valid rows in one DB transaction and return
        counts plus row-level rejection reasons. `transactions` is the primary use case; the
        same pipeline accepts every supplied dataset."""
        if dataset not in Dataset.values:
            raise ValidationError({"dataset": [f"must be one of {', '.join(Dataset.values)}"]})
        upload = ImportUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        file = upload.validated_data["file"]
        if file.size > settings.IMPORT_MAX_BYTES:
            raise ValidationError(
                {"file": [f"exceeds {settings.IMPORT_MAX_BYTES // 1024} KB limit"]}
            )
        if not file.name.lower().endswith(".csv"):
            raise ValidationError({"file": ["must be a .csv file"]})
        try:
            batch = run_import(dataset, file.read(), file_name=file.name, user=request.user)
        except DuplicateFileError as exc:
            raise ConflictError(str(exc)) from exc
        except InvalidFileError as exc:
            raise ValidationError({"file": [str(exc)]}) from exc
        return Response(ImportResultSerializer(batch).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["admin-imports"])
class ImportBatchListView(generics.ListAPIView):
    """Import history (most recent first)."""

    permission_classes = [IsAdminRole]
    serializer_class = ImportBatchSerializer
    queryset = ImportBatch.objects.select_related("created_by").order_by("-created_at")


@extend_schema(tags=["admin-imports"])
class ImportBatchDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = ImportResultSerializer
    queryset = ImportBatch.objects.select_related("created_by")
    lookup_url_kwarg = "batch_id"


@extend_schema(
    tags=["admin-imports"],
    parameters=[
        OpenApiParameter("outcome", enum=RowOutcome.values),
        OpenApiParameter("with_warnings", bool),
    ],
)
class ImportBatchRowsView(generics.ListAPIView):
    """Staged rows of one batch: the quarantine of rejected rows and their reasons."""

    permission_classes = [IsAdminRole]
    serializer_class = StagedRowSerializer

    def get_queryset(self):
        batch = get_object_or_404(ImportBatch, pk=self.kwargs["batch_id"])
        filters = RowFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        qs = batch.rows.order_by("row_number")
        if outcome := filters.validated_data.get("outcome"):
            qs = qs.filter(outcome=outcome)
        if filters.validated_data.get("with_warnings"):
            qs = qs.exclude(warnings=[])
        return qs
