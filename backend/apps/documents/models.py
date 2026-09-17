import uuid

from django.db import models


class FinanceDocumentMetadata(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.OneToOneField(
        "finance.FinanceDocument",
        on_delete=models.CASCADE,
        related_name="integrity_metadata",
    )
    mime_type = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField()
    checksum_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["checksum_sha256"], name="document_checksum_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.document.original_name} {self.checksum_sha256[:12]}"
