from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.ingestion.services import DuplicateFileError, InvalidFileError, run_import
from apps.ingestion.specs import SEED_ORDER


class Command(BaseCommand):
    help = (
        "Load the supplied CSV files through the same validation/staging pipeline as the admin "
        "import API. Safe to re-run: files already applied are skipped."
    )

    def add_arguments(self, parser):
        parser.add_argument("--data-dir", default="../data", help="Directory containing the CSVs")

    def handle(self, *args, data_dir, **options):
        directory = Path(data_dir)
        if not directory.is_dir():
            raise CommandError(f"Data directory {directory} does not exist")
        for dataset in SEED_ORDER:
            path = directory / f"{dataset.value}.csv"
            if not path.exists():
                raise CommandError(f"Missing {path}")
            try:
                batch = run_import(
                    dataset.value, path.read_bytes(), file_name=path.name, source="seed"
                )
            except DuplicateFileError as exc:
                self.stdout.write(
                    f"{dataset.value:<18} already loaded (batch {exc.batch.pk}), skipped"
                )
                continue
            except InvalidFileError as exc:
                raise CommandError(f"{dataset.value}: {exc}") from exc
            self.stdout.write(
                f"{dataset.value:<18} batch {batch.pk}: {batch.total_rows} rows, "
                f"{batch.inserted_rows} inserted, {batch.duplicate_rows} duplicate, "
                f"{batch.rejected_rows} rejected, {batch.warning_rows} with warnings"
            )
