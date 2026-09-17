import hashlib
import mimetypes

from django.core.management.base import BaseCommand

from apps.finance.models import FinanceDocument

from ...models import FinanceDocumentMetadata


class Command(BaseCommand):
    help = "Backfill MIME type, size, and SHA-256 metadata for existing finance documents."

    def handle(self, *args, **options):
        created = 0
        skipped = 0
        failed = 0

        queryset = FinanceDocument.objects.filter(integrity_metadata__isnull=True).order_by(
            "created_at"
        )
        for document in queryset:
            try:
                with document.file.open("rb") as file_handle:
                    hasher = hashlib.sha256()
                    size_bytes = 0
                    for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
                        hasher.update(chunk)
                        size_bytes += len(chunk)
                mime_type = mimetypes.guess_type(document.original_name)[0]
                FinanceDocumentMetadata.objects.create(
                    document=document,
                    mime_type=mime_type or "application/octet-stream",
                    size_bytes=size_bytes,
                    checksum_sha256=hasher.hexdigest(),
                )
                created += 1
            except FileNotFoundError:
                failed += 1
                self.stderr.write(f"Missing stored file for document {document.id}.")
            except OSError as exc:
                failed += 1
                self.stderr.write(f"Unable to inspect document {document.id}: {exc}")

        skipped = FinanceDocument.objects.exclude(integrity_metadata__isnull=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Document metadata backfill complete: {created} created, "
                f"{skipped} already present, {failed} failed."
            )
        )
