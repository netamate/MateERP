import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


DEFAULT_REMINDER_DAYS = [30, 15, 7, 3, 1, 0]


def seed_reminders_and_payment_history(apps, schema_editor):
    Subscription = apps.get_model("operations", "Subscription")
    SubscriptionPayment = apps.get_model("operations", "SubscriptionPayment")
    DomainRenewal = apps.get_model("operations", "DomainRenewal")

    Subscription.objects.filter(reminder_days=[]).update(
        reminder_days=DEFAULT_REMINDER_DAYS
    )

    for renewal in DomainRenewal.objects.select_related("domain").all():
        subscription = Subscription.objects.filter(
            legal_entity_id=renewal.legal_entity_id,
            name__iexact=renewal.domain.domain_name,
        ).first()
        if not subscription:
            continue
        SubscriptionPayment.objects.get_or_create(
            subscription_id=subscription.id,
            paid_on=renewal.renewed_on,
            previous_due_date=renewal.previous_expiry_date,
            next_due_date=renewal.new_expiry_date,
            amount=renewal.amount,
            currency=renewal.currency,
            defaults={
                "id": uuid.uuid4(),
                "legal_entity_id": renewal.legal_entity_id,
                "reference": "Legacy domain renewal",
                "notes": renewal.notes,
                "created_by_id": renewal.created_by_id,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("operations", "0002_unify_recurring_items"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="custom_cycle_days",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="subscription",
            name="hermes_target",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name="subscription",
            name="reminder_days",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="subscription",
            name="reminder_email",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="subscription",
            name="reminder_email_recipients",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="subscription",
            name="reminder_hermes",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="subscription",
            name="reminder_in_app",
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name="SubscriptionPayment",
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
                ("paid_on", models.DateField()),
                ("previous_due_date", models.DateField(blank=True, null=True)),
                ("next_due_date", models.DateField(blank=True, null=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=20)),
                ("currency", models.CharField(max_length=3)),
                ("reference", models.CharField(blank=True, max_length=255)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="recorded_subscription_payments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "legal_entity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscription_payments",
                        to="identity.legalentity",
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payments",
                        to="operations.subscription",
                    ),
                ),
            ],
            options={"ordering": ["-paid_on", "-created_at"]},
        ),
        migrations.RunPython(
            seed_reminders_and_payment_history,
            migrations.RunPython.noop,
        ),
        migrations.DeleteModel(name="DomainRenewal"),
        migrations.DeleteModel(name="Domain"),
        migrations.DeleteModel(name="InfrastructureAsset"),
    ]
