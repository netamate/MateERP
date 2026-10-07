import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class VendorConnectorType(models.TextChoices):
    GENERIC_JSON = "GENERIC_JSON", "Generic JSON API"


class VendorAuthType(models.TextChoices):
    NONE = "NONE", "No authentication"
    BEARER = "BEARER", "Bearer token"
    API_KEY_HEADER = "API_KEY_HEADER", "API key header"
    BASIC = "BASIC", "Basic authentication"


class SyncStatus(models.TextChoices):
    NEVER = "NEVER", "Never run"
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"


class RunStatus(models.TextChoices):
    RUNNING = "RUNNING", "Running"
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"
    SKIPPED = "SKIPPED", "Skipped"


class RunTrigger(models.TextChoices):
    MANUAL = "MANUAL", "Manual"
    SCHEDULED = "SCHEDULED", "Scheduled"


class AutomationKind(models.TextChoices):
    ENSURE_PAYG_PERIODS = "ENSURE_PAYG_PERIODS", "Ensure PAYG billing periods"
    SYNC_VENDOR_USAGE = "SYNC_VENDOR_USAGE", "Sync vendor usage"
    REFRESH_ALERTS = "REFRESH_ALERTS", "Refresh alert rules"


class AutomationFrequency(models.TextChoices):
    HOURLY = "HOURLY", "Hourly"
    DAILY = "DAILY", "Daily"


class VendorIntegration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "identity.Organization",
        on_delete=models.CASCADE,
        related_name="vendor_integrations",
    )
    legal_entity = models.ForeignKey(
        "identity.LegalEntity",
        on_delete=models.CASCADE,
        related_name="vendor_integrations",
    )
    vendor = models.ForeignKey(
        "finance.Vendor",
        on_delete=models.PROTECT,
        related_name="api_integrations",
    )
    subscription = models.OneToOneField(
        "operations.Subscription",
        on_delete=models.PROTECT,
        related_name="vendor_integration",
    )
    name = models.CharField(max_length=180)
    connector_type = models.CharField(
        max_length=32,
        choices=VendorConnectorType.choices,
        default=VendorConnectorType.GENERIC_JSON,
    )
    enabled = models.BooleanField(default=True)
    endpoint_url = models.URLField(max_length=1000)
    auth_type = models.CharField(
        max_length=24,
        choices=VendorAuthType.choices,
        default=VendorAuthType.NONE,
    )
    auth_username = models.CharField(max_length=180, blank=True)
    secret_encrypted = models.TextField(blank=True)
    api_key_header = models.CharField(max_length=120, default="X-API-Key", blank=True)
    custom_headers = models.JSONField(default=dict, blank=True)
    cost_json_path = models.CharField(max_length=255)
    usage_quantity_json_path = models.CharField(max_length=255, blank=True)
    currency_json_path = models.CharField(max_length=255, blank=True)
    usage_unit_json_path = models.CharField(max_length=255, blank=True)
    timeout_seconds = models.PositiveSmallIntegerField(default=15)
    auto_create_period = models.BooleanField(default=True)
    last_test_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(
        max_length=16,
        choices=SyncStatus.choices,
        default=SyncStatus.NEVER,
    )
    last_test_error = models.TextField(blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(
        max_length=16,
        choices=SyncStatus.choices,
        default=SyncStatus.NEVER,
    )
    last_sync_error = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_vendor_integrations",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="updated_vendor_integrations",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["vendor__name", "name"]
        indexes = [
            models.Index(
                fields=["organization", "enabled"],
                name="vendor_int_org_enabled_idx",
            ),
            models.Index(
                fields=["legal_entity", "enabled"],
                name="vendor_int_entity_enabled_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.vendor.name} · {self.name}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.legal_entity_id and self.legal_entity.organization_id != self.organization_id:
            raise ValidationError("Integration legal entity must belong to the organization.")
        if self.vendor_id and self.vendor.legal_entity_id != self.legal_entity_id:
            raise ValidationError("Vendor must belong to the integration legal entity.")
        if self.subscription_id:
            if self.subscription.legal_entity_id != self.legal_entity_id:
                raise ValidationError("Subscription must belong to the integration legal entity.")
            if self.subscription.vendor_id and self.subscription.vendor_id != self.vendor_id:
                raise ValidationError("Subscription vendor must match the integration vendor.")
            if self.subscription.billing_mode != "PAYG":
                raise ValidationError("Vendor usage integrations require a PAYG subscription.")
        if self.timeout_seconds < 3 or self.timeout_seconds > 60:
            raise ValidationError("Timeout must be between 3 and 60 seconds.")
        if self.auth_type == VendorAuthType.BASIC and not self.auth_username.strip():
            raise ValidationError("Basic authentication requires a username.")
        if self.auth_type == VendorAuthType.API_KEY_HEADER:
            header = self.api_key_header.strip()
            if not header or not header.replace("-", "").isalnum():
                raise ValidationError("API key header contains invalid characters.")
            if header.lower() in {"authorization", "cookie", "host"}:
                raise ValidationError("Use a dedicated API key header, not a protected header.")
        if not isinstance(self.custom_headers, dict):
            raise ValidationError("Custom headers must be an object.")
        protected = {"authorization", "cookie", "host", "content-length"}
        if any(str(key).lower() in protected for key in self.custom_headers):
            raise ValidationError("Protected HTTP headers cannot be overridden.")


class VendorSyncRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(
        VendorIntegration,
        on_delete=models.CASCADE,
        related_name="sync_runs",
    )
    trigger = models.CharField(max_length=16, choices=RunTrigger.choices)
    status = models.CharField(
        max_length=16,
        choices=RunStatus.choices,
        default=RunStatus.RUNNING,
    )
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    billing_period = models.ForeignKey(
        "operations.SubscriptionBillingPeriod",
        on_delete=models.SET_NULL,
        related_name="vendor_sync_runs",
        null=True,
        blank=True,
    )
    cost_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    usage_quantity = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3, blank=True)
    usage_unit = models.CharField(max_length=40, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="initiated_vendor_sync_runs",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(
                fields=["integration", "status", "started_at"],
                name="vendor_sync_status_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.integration.name} · {self.status} · {self.started_at}"


class AutomationPolicy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "identity.Organization",
        on_delete=models.CASCADE,
        related_name="automation_policies",
    )
    legal_entity = models.ForeignKey(
        "identity.LegalEntity",
        on_delete=models.CASCADE,
        related_name="automation_policies",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=180)
    kind = models.CharField(max_length=32, choices=AutomationKind.choices)
    enabled = models.BooleanField(default=True)
    frequency = models.CharField(
        max_length=16,
        choices=AutomationFrequency.choices,
        default=AutomationFrequency.DAILY,
    )
    schedule_hour = models.PositiveSmallIntegerField(default=0)
    schedule_timezone = models.CharField(max_length=64, default="UTC")
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(
        max_length=16,
        choices=RunStatus.choices,
        default=RunStatus.SKIPPED,
    )
    last_summary = models.JSONField(default=dict, blank=True)
    last_error = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_automation_policies",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="updated_automation_policies",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kind", "legal_entity_id", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "legal_entity", "kind"],
                name="uniq_automation_scope_kind",
                nulls_distinct=False,
            )
        ]
        indexes = [
            models.Index(
                fields=["organization", "enabled", "kind"],
                name="automation_org_kind_idx",
            )
        ]

    def __str__(self) -> str:
        scope = self.legal_entity.name if self.legal_entity_id else self.organization.name
        return f"{scope} · {self.name}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.legal_entity_id and self.legal_entity.organization_id != self.organization_id:
            raise ValidationError("Automation legal entity must belong to the organization.")
        if self.schedule_hour > 23:
            raise ValidationError("Schedule hour must be between 0 and 23.")
        try:
            ZoneInfo(self.schedule_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValidationError("Schedule timezone is not a valid IANA timezone.") from exc


class AutomationRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy = models.ForeignKey(
        AutomationPolicy,
        on_delete=models.CASCADE,
        related_name="runs",
    )
    trigger = models.CharField(max_length=16, choices=RunTrigger.choices)
    status = models.CharField(
        max_length=16,
        choices=RunStatus.choices,
        default=RunStatus.RUNNING,
    )
    summary = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="initiated_automation_runs",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(
                fields=["policy", "status", "started_at"],
                name="automation_run_status_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.policy.name} · {self.status} · {self.started_at}"
