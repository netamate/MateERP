"""Add service catalogue and account identities without discarding legacy subscriptions."""

import uuid

import django.db.models.deletion
from django.db import migrations, models


def backfill_subscription_codes(apps, schema_editor):
    Subscription = apps.get_model("operations", "Subscription")
    db = schema_editor.connection.alias
    for subscription in Subscription.objects.using(db).only("id").iterator():
        # UUID-derived, immutable and independent of account aliases or service names.
        code = f"SUB-{subscription.id.hex[:16].upper()}"
        Subscription.objects.using(db).filter(pk=subscription.pk).update(subscription_code=code)


class Migration(migrations.Migration):
    dependencies = [
        ("operations", "0003_alerts_payments_and_legacy_cleanup"),
    ]

    operations = [
        migrations.CreateModel(
            name="VendorService",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("code", models.CharField(max_length=40)),
                ("name", models.CharField(max_length=180)),
                (
                    "service_type",
                    models.CharField(
                        choices=[
                            ("DOMAIN", "Domain"),
                            ("VPS", "VPS / Server"),
                            ("CLOUD", "Cloud"),
                            ("HOSTING", "Hosting"),
                            ("SAAS", "SaaS / Software"),
                            ("API", "API / Usage Service"),
                            ("STORAGE", "Storage / Backup"),
                            ("EMAIL", "Email Service"),
                            ("AI", "AI Service"),
                            ("OTHER", "Other"),
                        ],
                        default="OTHER",
                        max_length=20,
                    ),
                ),
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
                        related_name="vendor_services",
                        to="identity.legalentity",
                    ),
                ),
                (
                    "vendor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="services",
                        to="finance.vendor",
                    ),
                ),
            ],
            options={"ordering": ["vendor__name", "name"]},
        ),
        migrations.CreateModel(
            name="ServiceAccount",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("code", models.CharField(editable=False, max_length=20, unique=True)),
                ("alias", models.CharField(max_length=120)),
                ("reference", models.CharField(blank=True, max_length=180)),
                (
                    "status",
                    models.CharField(
                        choices=[("ACTIVE", "Active"), ("ARCHIVED", "Archived")],
                        default="ACTIVE",
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
                        related_name="service_accounts",
                        to="identity.legalentity",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="accounts",
                        to="operations.vendorservice",
                    ),
                ),
            ],
            options={"ordering": ["service__name", "alias"]},
        ),
        migrations.AddField(
            model_name="subscription",
            name="service",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="subscriptions",
                to="operations.vendorservice",
            ),
        ),
        migrations.AddField(
            model_name="subscription",
            name="service_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="subscriptions",
                to="operations.serviceaccount",
            ),
        ),
        migrations.AddField(
            model_name="subscription",
            name="subscription_code",
            field=models.CharField(editable=False, max_length=20, null=True, unique=True),
        ),
        migrations.RunPython(backfill_subscription_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="subscription",
            name="subscription_code",
            field=models.CharField(editable=False, max_length=20, unique=True),
        ),
        migrations.RemoveConstraint(
            model_name="subscription",
            name="uniq_subscription_name_per_entity",
        ),
        migrations.AddConstraint(
            model_name="vendorservice",
            constraint=models.UniqueConstraint(
                fields=("legal_entity", "vendor", "code"), name="uniq_vendor_service_code"
            ),
        ),
        migrations.AddConstraint(
            model_name="serviceaccount",
            constraint=models.UniqueConstraint(
                models.functions.Lower("alias"),
                "service",
                name="uniq_service_account_alias_ci",
            ),
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(
                fields=("legal_entity", "name"),
                condition=models.Q(service_account__isnull=True),
                name="uniq_unassigned_subscription_name",
            ),
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(
                fields=("legal_entity", "service_account", "name"),
                condition=models.Q(service_account__isnull=False),
                name="uniq_subscription_name_per_account",
            ),
        ),
    ]
