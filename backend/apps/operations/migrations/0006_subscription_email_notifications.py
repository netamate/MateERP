from django.db import migrations, models


def copy_legacy_email_toggle(apps, schema_editor):
    Subscription = apps.get_model("operations", "Subscription")
    Subscription.objects.filter(reminder_email=True).update(email_notifications_enabled=True)


class Migration(migrations.Migration):

    dependencies = [
        ("operations", "0005_payg_billing_reconciliation"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="email_notifications_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(copy_legacy_email_toggle, migrations.RunPython.noop),
    ]
