from rest_framework import serializers

from .models import Dataset, ImportBatch, RowOutcome, StagedRow


class StagedRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = StagedRow
        fields = ["row_number", "record_key", "outcome", "errors", "warnings", "raw"]


class ImportBatchSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", default=None, read_only=True)

    class Meta:
        model = ImportBatch
        fields = [
            "id",
            "dataset",
            "source",
            "file_name",
            "file_sha256",
            "status",
            "total_rows",
            "inserted_rows",
            "duplicate_rows",
            "rejected_rows",
            "warning_rows",
            "error_message",
            "created_by",
            "created_at",
            "finished_at",
        ]


class ImportResultSerializer(ImportBatchSerializer):
    rejected = serializers.SerializerMethodField(help_text="First 200 rejected rows with reasons")

    class Meta(ImportBatchSerializer.Meta):
        fields = [*ImportBatchSerializer.Meta.fields, "rejected"]

    def get_rejected(self, obj) -> StagedRowSerializer(many=True):  # type: ignore[valid-type]
        rows = obj.rows.filter(outcome=RowOutcome.REJECTED).order_by("row_number")[:200]
        return StagedRowSerializer(rows, many=True).data


class ImportUploadSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="UTF-8 CSV with a header row")


class RowFilterSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=RowOutcome.choices, required=False)
    with_warnings = serializers.BooleanField(required=False)


DATASET_CHOICES = Dataset.values
