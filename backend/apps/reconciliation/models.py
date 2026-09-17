import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.accounting.models import JournalLine
from apps.finance.models import FinancialAccount
from apps.identity.models import LegalEntity


class ReconciliationStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    COMPLETED = "COMPLETED", "Completed"


class AccountReconciliation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="account_reconciliations",
    )
    financial_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="reconciliations",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    statement_ending_balance = models.DecimalField(max_digits=20, decimal_places=2)
    status = models.CharField(
        max_length=16,
        choices=ReconciliationStatus.choices,
        default=ReconciliationStatus.DRAFT,
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_reconciliations",
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="completed_reconciliations",
        null=True,
        blank=True,
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-end_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["financial_account", "start_date", "end_date"],
                name="uniq_reconciliation_period_per_account",
            )
        ]
        indexes = [
            models.Index(
                fields=["legal_entity", "status", "end_date"],
                name="recon_entity_status_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.financial_account} {self.start_date} - {self.end_date}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == ReconciliationStatus.COMPLETED:
            raise ValidationError("Completed reconciliations cannot be deleted.")
        return super().delete(*args, **kwargs)

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError("Reconciliation end date cannot be before the start date.")
        if (
            self.financial_account_id
            and self.financial_account.legal_entity_id != self.legal_entity_id
        ):
            raise ValidationError("Financial account must belong to the reconciliation legal entity.")


class ReconciliationItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reconciliation = models.ForeignKey(
        AccountReconciliation,
        on_delete=models.CASCADE,
        related_name="items",
    )
    journal_line = models.OneToOneField(
        JournalLine,
        on_delete=models.PROTECT,
        related_name="reconciliation_item",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["journal_line__journal_entry__entry_date", "created_at"]

    def __str__(self) -> str:
        return f"{self.reconciliation_id}: {self.journal_line_id}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.reconciliation.status == ReconciliationStatus.COMPLETED:
            raise ValidationError("Completed reconciliation items are immutable.")
        return super().delete(*args, **kwargs)

    def clean(self):
        if not self.reconciliation_id or not self.journal_line_id:
            return
        if self.reconciliation.status == ReconciliationStatus.COMPLETED:
            raise ValidationError("Completed reconciliation items are immutable.")
        account = self.reconciliation.financial_account
        line = self.journal_line
        if line.journal_entry.legal_entity_id != self.reconciliation.legal_entity_id:
            raise ValidationError("Journal line must belong to the reconciliation legal entity.")
        if line.account_id != account.ledger_account_id:
            raise ValidationError("Journal line must belong to the reconciled financial account.")
        if not (
            self.reconciliation.start_date
            <= line.journal_entry.entry_date
            <= self.reconciliation.end_date
        ):
            raise ValidationError("Journal line must fall inside the reconciliation period.")
        if line.currency != account.currency:
            raise ValidationError("Journal line currency must match the financial account currency.")
