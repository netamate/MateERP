import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("finance", "0002_document_library"),
        ("identity", "0001_initial"),
        ("operations", "0005_payg_billing_reconciliation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AutomationPolicy",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("kind", models.CharField(choices=[("ENSURE_PAYG_PERIODS", "Ensure PAYG billing periods"), ("SYNC_VENDOR_USAGE", "Sync vendor usage"), ("REFRESH_ALERTS", "Refresh alert rules")], max_length=32)),
                ("enabled", models.BooleanField(default=True)),
                ("frequency", models.CharField(choices=[("HOURLY", "Hourly"), ("DAILY", "Daily")], default="DAILY", max_length=16)),
                ("schedule_hour", models.PositiveSmallIntegerField(default=0)),
                ("schedule_timezone", models.CharField(default="UTC", max_length=64)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("last_status", models.CharField(choices=[("RUNNING", "Running"), ("SUCCESS", "Success"), ("FAILED", "Failed"), ("SKIPPED", "Skipped")], default="SKIPPED", max_length=16)),
                ("last_summary", models.JSONField(blank=True, default=dict)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_automation_policies", to=settings.AUTH_USER_MODEL)),
                ("legal_entity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="automation_policies", to="identity.legalentity")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="automation_policies", to="identity.organization")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_automation_policies", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["kind", "legal_entity_id", "name"]},
        ),
        migrations.CreateModel(
            name="VendorIntegration",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("connector_type", models.CharField(choices=[("GENERIC_JSON", "Generic JSON API")], default="GENERIC_JSON", max_length=32)),
                ("enabled", models.BooleanField(default=True)),
                ("endpoint_url", models.URLField(max_length=1000)),
                ("auth_type", models.CharField(choices=[("NONE", "No authentication"), ("BEARER", "Bearer token"), ("API_KEY_HEADER", "API key header"), ("BASIC", "Basic authentication")], default="NONE", max_length=24)),
                ("auth_username", models.CharField(blank=True, max_length=180)),
                ("secret_encrypted", models.TextField(blank=True)),
                ("api_key_header", models.CharField(blank=True, default="X-API-Key", max_length=120)),
                ("custom_headers", models.JSONField(blank=True, default=dict)),
                ("cost_json_path", models.CharField(max_length=255)),
                ("usage_quantity_json_path", models.CharField(blank=True, max_length=255)),
                ("currency_json_path", models.CharField(blank=True, max_length=255)),
                ("usage_unit_json_path", models.CharField(blank=True, max_length=255)),
                ("timeout_seconds", models.PositiveSmallIntegerField(default=15)),
                ("auto_create_period", models.BooleanField(default=True)),
                ("last_test_at", models.DateTimeField(blank=True, null=True)),
                ("last_test_status", models.CharField(choices=[("NEVER", "Never run"), ("SUCCESS", "Success"), ("FAILED", "Failed")], default="NEVER", max_length=16)),
                ("last_test_error", models.TextField(blank=True)),
                ("last_sync_at", models.DateTimeField(blank=True, null=True)),
                ("last_sync_status", models.CharField(choices=[("NEVER", "Never run"), ("SUCCESS", "Success"), ("FAILED", "Failed")], default="NEVER", max_length=16)),
                ("last_sync_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_vendor_integrations", to=settings.AUTH_USER_MODEL)),
                ("legal_entity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vendor_integrations", to="identity.legalentity")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vendor_integrations", to="identity.organization")),
                ("subscription", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="vendor_integration", to="operations.subscription")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_vendor_integrations", to=settings.AUTH_USER_MODEL)),
                ("vendor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="api_integrations", to="finance.vendor")),
            ],
            options={"ordering": ["vendor__name", "name"]},
        ),
        migrations.CreateModel(
            name="AutomationRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("trigger", models.CharField(choices=[("MANUAL", "Manual"), ("SCHEDULED", "Scheduled")], max_length=16)),
                ("status", models.CharField(choices=[("RUNNING", "Running"), ("SUCCESS", "Success"), ("FAILED", "Failed"), ("SKIPPED", "Skipped")], default="RUNNING", max_length=16)),
                ("summary", models.JSONField(blank=True, default=dict)),
                ("error", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("initiated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="initiated_automation_runs", to=settings.AUTH_USER_MODEL)),
                ("policy", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="runs", to="automation.automationpolicy")),
            ],
            options={"ordering": ["-started_at"]},
        ),
        migrations.CreateModel(
            name="VendorSyncRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("trigger", models.CharField(choices=[("MANUAL", "Manual"), ("SCHEDULED", "Scheduled")], max_length=16)),
                ("status", models.CharField(choices=[("RUNNING", "Running"), ("SUCCESS", "Success"), ("FAILED", "Failed"), ("SKIPPED", "Skipped")], default="RUNNING", max_length=16)),
                ("http_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("cost_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True)),
                ("usage_quantity", models.DecimalField(blank=True, decimal_places=4, max_digits=20, null=True)),
                ("currency", models.CharField(blank=True, max_length=3)),
                ("usage_unit", models.CharField(blank=True, max_length=40)),
                ("error", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("billing_period", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vendor_sync_runs", to="operations.subscriptionbillingperiod")),
                ("initiated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="initiated_vendor_sync_runs", to=settings.AUTH_USER_MODEL)),
                ("integration", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sync_runs", to="automation.vendorintegration")),
            ],
            options={"ordering": ["-started_at"]},
        ),
        migrations.AddConstraint(
            model_name="automationpolicy",
            constraint=models.UniqueConstraint(fields=("organization", "legal_entity", "kind"), name="uniq_automation_scope_kind", nulls_distinct=False),
        ),
        migrations.AddIndex(
            model_name="automationpolicy",
            index=models.Index(fields=["organization", "enabled", "kind"], name="automation_org_kind_idx"),
        ),
        migrations.AddIndex(
            model_name="automationrun",
            index=models.Index(fields=["policy", "status", "started_at"], name="automation_run_status_idx"),
        ),
        migrations.AddIndex(
            model_name="vendorintegration",
            index=models.Index(fields=["organization", "enabled"], name="vendor_int_org_enabled_idx"),
        ),
        migrations.AddIndex(
            model_name="vendorintegration",
            index=models.Index(fields=["legal_entity", "enabled"], name="vendor_int_entity_enabled_idx"),
        ),
        migrations.AddIndex(
            model_name="vendorsyncrun",
            index=models.Index(fields=["integration", "status", "started_at"], name="vendor_sync_status_idx"),
        ),
    ]
