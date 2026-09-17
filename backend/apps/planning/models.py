import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.accounting.models import Account, AccountType
from apps.finance.models import Expense
from apps.identity.models import LegalEntity


class MasterDataStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    ARCHIVED = "ARCHIVED", "Archived"


class ProjectStatus(models.TextChoices):
    PLANNED = "PLANNED", "Planned"
    ACTIVE = "ACTIVE", "Active"
    COMPLETED = "COMPLETED", "Completed"
    ARCHIVED = "ARCHIVED", "Archived"


class BudgetStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    CLOSED = "CLOSED", "Closed"


class CostCenter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="cost_centers",
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=MasterDataStatus.choices,
        default=MasterDataStatus.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["legal_entity", "code"],
                name="uniq_cost_center_code_per_entity",
            )
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        self.full_clean()
        super().save(*args, **kwargs)


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="products",
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=MasterDataStatus.choices,
        default=MasterDataStatus.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["legal_entity", "code"],
                name="uniq_product_code_per_entity",
            )
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        self.full_clean()
        super().save(*args, **kwargs)


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="projects",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="projects",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=180)
    client_name = models.CharField(max_length=180, blank=True)
    description = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=ProjectStatus.choices,
        default=ProjectStatus.PLANNED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["legal_entity", "code"],
                name="uniq_project_code_per_entity",
            )
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.product_id and self.product.legal_entity_id != self.legal_entity_id:
            raise ValidationError("Project product must belong to the same legal entity.")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("Project end date cannot be before the start date.")


class ExpenseAllocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="expense_allocations",
    )
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    cost_center = models.ForeignKey(
        CostCenter,
        on_delete=models.PROTECT,
        related_name="expense_allocations",
        null=True,
        blank=True,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="expense_allocations",
        null=True,
        blank=True,
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="expense_allocations",
        null=True,
        blank=True,
    )
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    base_amount = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_expense_allocations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="expense_allocation_amount_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(cost_center__isnull=False)
                    | Q(product__isnull=False)
                    | Q(project__isnull=False)
                ),
                name="expense_allocation_has_dimension",
            ),
        ]

    def __str__(self) -> str:
        return f"Allocation {self.amount} for {self.expense_id}"

    def save(self, *args, **kwargs):
        if self.expense_id:
            self.base_amount = (self.amount * self.expense.fx_rate).quantize(Decimal("0.01"))
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.amount <= 0:
            raise ValidationError("Allocation amount must be greater than zero.")
        if not any((self.cost_center_id, self.product_id, self.project_id)):
            raise ValidationError("Allocation requires at least one planning dimension.")
        if self.expense_id and self.expense.legal_entity_id != self.legal_entity_id:
            raise ValidationError("Expense must belong to the same legal entity.")
        for dimension in (self.cost_center, self.product, self.project):
            if dimension and dimension.legal_entity_id != self.legal_entity_id:
                raise ValidationError("Allocation dimensions must belong to the same legal entity.")


class Budget(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="budgets",
    )
    name = models.CharField(max_length=180)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=16,
        choices=BudgetStatus.choices,
        default=BudgetStatus.DRAFT,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["legal_entity", "name", "start_date", "end_date"],
                name="uniq_budget_period_name_per_entity",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError("Budget end date cannot be before the start date.")


class BudgetLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    budget = models.ForeignKey(
        Budget,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    expense_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="budget_lines",
        null=True,
        blank=True,
    )
    cost_center = models.ForeignKey(
        CostCenter,
        on_delete=models.PROTECT,
        related_name="budget_lines",
        null=True,
        blank=True,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="budget_lines",
        null=True,
        blank=True,
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="budget_lines",
        null=True,
        blank=True,
    )
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="budget_line_amount_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(expense_account__isnull=False)
                    | Q(cost_center__isnull=False)
                    | Q(product__isnull=False)
                    | Q(project__isnull=False)
                ),
                name="budget_line_has_target",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.budget.name}: {self.amount}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.amount <= 0:
            raise ValidationError("Budget line amount must be greater than zero.")
        if not any(
            (self.expense_account_id, self.cost_center_id, self.product_id, self.project_id)
        ):
            raise ValidationError("Budget line requires at least one target dimension.")
        legal_entity_id = self.budget.legal_entity_id if self.budget_id else None
        if self.expense_account_id:
            if self.expense_account.legal_entity_id != legal_entity_id:
                raise ValidationError("Budget account must belong to the same legal entity.")
            if self.expense_account.account_type != AccountType.EXPENSE:
                raise ValidationError("Budget account must be an expense account.")
        for dimension in (self.cost_center, self.product, self.project):
            if dimension and dimension.legal_entity_id != legal_entity_id:
                raise ValidationError("Budget dimensions must belong to the same legal entity.")
