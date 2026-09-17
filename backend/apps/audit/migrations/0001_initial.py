import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("action", models.CharField(max_length=120)),
                ("object_type", models.CharField(max_length=120)),
                ("object_id", models.CharField(max_length=64)),
                ("previous_state", models.JSONField(blank=True, default=dict)),
                ("new_state", models.JSONField(blank=True, default=dict)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("request_id", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_events", to=settings.AUTH_USER_MODEL)),
                ("legal_entity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="audit_events", to="identity.legalentity")),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="audit_events", to="identity.organization")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["organization", "created_at"], name="audit_org_created_idx"),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["object_type", "object_id"], name="audit_object_idx"),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["action", "created_at"], name="audit_action_created_idx"),
        ),
    ]
