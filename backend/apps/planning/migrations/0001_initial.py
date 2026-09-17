import decimal
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounting", "0001_initial"),
        ("finance", "0001_initial"),
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Budget",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[("DRAFT", "Draft"), ("ACTIVE", "Active"), ("CLOSED", "Closed")],
                        default="DRAFT",
                        max_length=16,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "legal_entity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="budgets",
                        to="identity.legalentity",
                    ),
                ),
            ],
            options={
                "ordering": ["-start_date", "name"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("legal_entity", "name", "start_date", "end_date"),
                        name="uniq_budget_period_name_per_entity",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="CostCenter",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=32)),
                ("name", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("ACTIVE", "Active"), ("ARCHIVED", "Archived")],
                        default="ACTIVE",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "legal_entity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cost_centers",
                        to="identity.legalentity",
                    ),
                ),
            ],
            options={
                "ordering": ["code"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("legal_entity", "code"),
                        name="uniq_cost_center_code_per_entity",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=32)),
                ("name", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("ACTIVE", "Active"), ("ARCHIVED", "Archived")],
                        default="ACTIVE",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "legal_entity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="products",
                        to="identity.legalentity",
                    ),
                ),
            ],
            options={
                "ordering": ["code"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("legal_entity", "code"),
                        name="uniq_product_code_per_entity",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Project",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=32)),
                ("name", models.CharField(max_length=180)),
                ("client_name", models.CharField(blank=True, max_length=180)),
                ("description", models.TextField(blank=True)),
                ("start_date", models.DateField(blank=True, null=True)),
                ("end_date", models.DateField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PLANNED", "Planned"),
                            ("ACTIVE", "Active"),
                            ("COMPLETED", "Completed"),
                            ("ARCHIVED", "Archived"),
                        ],
                        default="PLANNED",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "legal_entity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="projects",
                        to="identity.legalentity",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="projects",
                        to="planning.product",
                    ),
                ),
            ],
            options={
                "ordering": ["code"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("legal_entity", "code"),
                        name="uniq_project_code_per_entity",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ExpenseAllocation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=20)),
                (
                    "base_amount",
                    models.DecimalField(decimal_places=2, default=decimal.Decimal("0"), max_digits=20),
                ),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "cost_center",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="expense_allocations",
                        to="planning.costcenter",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_expense_allocations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "expense",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="allocations",
                        to="finance.expense",
                    ),
                ),
                (
                    "legal_entity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="expense_allocations",
                        to="identity.legalentity",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="expense_allocations",
                        to="planning.product",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="expense_allocations",
                        to="planning.project",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("amount__gt", 0)),
                        name="expense_allocation_amount_positive",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(("cost_center__isnull", False))
                            | models.Q(("product__isnull", False))
                            | models.Q(("project__isnull", False))
                        ),
                        name="expense_allocation_has_dimension",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="BudgetLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=20)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "budget",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lines",
                        to="planning.budget",
                    ),
                ),
                (
                    "cost_center",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="budget_lines",
                        to="planning.costcenter",
                    ),
                ),
                (
                    "expense_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="budget_lines",
                        to="accounting.account",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="budget_lines",
                        to="planning.product",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="budget_lines",
                        to="planning.project",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("amount__gt", 0)),
                        name="budget_line_amount_positive",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(("expense_account__isnull", False))
                            | models.Q(("cost_center__isnull", False))
                            | models.Q(("product__isnull", False))
                            | models.Q(("project__isnull", False))
                        ),
                        name="budget_line_has_target",
                    ),
                ],
            },
        ),
    ]
