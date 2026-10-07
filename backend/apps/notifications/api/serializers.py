from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework import serializers

from apps.identity.models import Membership, MembershipStatus
from apps.identity.policy import Permission, has_permission

from ..models import (
    AlertRule,
    Notification,
    NotificationDelivery,
    NotificationKind,
)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "kind",
            "legal_entity",
            "severity",
            "title",
            "message",
            "email_subject",
            "email_text_body",
            "email_html_body",
            "link",
            "due_date",
            "read_at",
            "resolved_at",
            "created_at",
        ]
        read_only_fields = fields


class NotificationDeliverySerializer(serializers.ModelSerializer):
    subscription_name = serializers.CharField(
        source="subscription.name",
        read_only=True,
        allow_null=True,
    )
    alert_rule_name = serializers.CharField(
        source="alert_rule.name",
        read_only=True,
        allow_null=True,
    )
    source_label = serializers.SerializerMethodField()
    email_template_name = serializers.CharField(
        source="email_template.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = NotificationDelivery
        fields = [
            "id",
            "subscription",
            "subscription_name",
            "alert_rule",
            "alert_rule_name",
            "email_template",
            "email_template_name",
            "email_template_version",
            "signal",
            "source_type",
            "source_id",
            "source_label",
            "channel",
            "destination",
            "reminder_days_before",
            "due_date",
            "severity",
            "title",
            "message",
            "link",
            "status",
            "attempt_count",
            "last_error",
            "sent_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_source_label(self, obj):
        if obj.subscription_id:
            return obj.subscription.name
        if obj.source_type and obj.source_id:
            return f"{obj.source_type} · {obj.source_id[:8]}"
        return obj.signal


class AlertRuleSerializer(serializers.ModelSerializer):
    legal_entity_name = serializers.CharField(
        source="legal_entity.name",
        read_only=True,
        allow_null=True,
    )
    recipient_users = serializers.SerializerMethodField()
    email_template_name = serializers.CharField(
        source="email_template.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = AlertRule
        exclude = ["organization", "created_by", "updated_by"]
        read_only_fields = [
            "id",
            "last_evaluated_at",
            "last_delivery_count",
            "last_failure_count",
            "last_error",
            "created_at",
            "updated_at",
            "legal_entity_name",
            "recipient_users",
            "email_template_name",
        ]

    def get_recipient_users(self, obj):
        if not obj.recipient_user_ids:
            return []
        selected = {str(value) for value in obj.recipient_user_ids}
        memberships = Membership.objects.filter(
            organization=obj.organization,
            status=MembershipStatus.ACTIVE,
        ).select_related("user")
        return [
            {
                "id": str(membership.user_id),
                "email": membership.user.email,
                "display_name": membership.user.display_name,
            }
            for membership in memberships
            if str(membership.user_id) in selected
        ]

    def validate_schedule_timezone(self, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise serializers.ValidationError(
                "Use a valid IANA timezone, for example Asia/Dhaka or UTC."
            ) from exc
        return value

    def validate_renewal_days(self, value):
        normalized = []
        for item in value:
            if not isinstance(item, int) or isinstance(item, bool) or item < 0 or item > 365:
                raise serializers.ValidationError(
                    "Renewal offsets must be integer days between 0 and 365."
                )
            if item not in normalized:
                normalized.append(item)
        return sorted(normalized, reverse=True)

    def validate_email_recipients(self, value):
        field = serializers.EmailField()
        normalized = []
        for item in value:
            email = field.run_validation(item).lower()
            if email not in normalized:
                normalized.append(email)
        return normalized

    def validate_recipient_user_ids(self, value):
        organization = self.context.get("organization")
        if organization is None:
            return value
        selected = {str(item) for item in value}
        memberships = Membership.objects.filter(
            organization=organization,
            status=MembershipStatus.ACTIVE,
        ).select_related("user")
        allowed = {
            str(membership.user_id)
            for membership in memberships
            if has_permission(membership, Permission.VIEW_NOTIFICATIONS)
        }
        invalid = selected - allowed
        if invalid:
            raise serializers.ValidationError(
                "Every selected recipient must be an active organization member "
                "with notification access."
            )
        return sorted(selected)

    def validate(self, attrs):
        organization = self.context.get("organization")
        entity = attrs.get("legal_entity", getattr(self.instance, "legal_entity", None))
        if entity and organization and entity.organization_id != organization.id:
            raise serializers.ValidationError(
                {"legal_entity": "Choose a legal entity from this organization."}
            )
        signal = attrs.get("signal", getattr(self.instance, "signal", None))
        supported = {
            NotificationKind.RENEWAL_DUE,
            NotificationKind.BUDGET_THRESHOLD,
            NotificationKind.MISSING_INVOICE,
            NotificationKind.INVOICE_OVERDUE,
            NotificationKind.RECONCILIATION_NEEDED,
        }
        if signal not in supported:
            raise serializers.ValidationError({"signal": "Unsupported alert signal."})
        if self.instance and "signal" in attrs and signal != self.instance.signal:
            raise serializers.ValidationError(
                {"signal": "Change alert scope by creating a new rule instead."}
            )
        if attrs.get("schedule_hour", getattr(self.instance, "schedule_hour", 8)) > 23:
            raise serializers.ValidationError(
                {"schedule_hour": "Schedule hour must be between 0 and 23."}
            )
        email_template = attrs.get(
            "email_template",
            getattr(self.instance, "email_template", None),
        )
        if email_template:
            if organization and email_template.organization_id != organization.id:
                raise serializers.ValidationError(
                    {"email_template": "Template belongs to another organization."}
                )
            if email_template.status != "ACTIVE":
                raise serializers.ValidationError(
                    {"email_template": "Choose an active email template."}
                )
            if email_template.signal not in {None, signal}:
                raise serializers.ValidationError(
                    {"email_template": "Template signal does not match this alert rule."}
                )
            if (
                email_template.legal_entity_id
                and entity
                and email_template.legal_entity_id != entity.id
            ):
                raise serializers.ValidationError(
                    {"email_template": "Template belongs to a different legal entity."}
                )
            if email_template.legal_entity_id and entity is None:
                raise serializers.ValidationError(
                    {
                        "email_template": (
                            "Organization-level rules can use organization-level templates only."
                        )
                    }
                )
        return attrs


class NotificationIntegrationSettingsSerializer(serializers.Serializer):
    smtp_enabled = serializers.BooleanField(required=False)
    smtp_host = serializers.CharField(required=False, allow_blank=True, max_length=255)
    smtp_port = serializers.IntegerField(required=False, min_value=1, max_value=65535)
    smtp_username = serializers.CharField(required=False, allow_blank=True, max_length=255)
    smtp_password = serializers.CharField(
        required=False,
        allow_blank=False,
        write_only=True,
        max_length=1024,
    )
    smtp_use_tls = serializers.BooleanField(required=False)
    smtp_use_ssl = serializers.BooleanField(required=False)
    smtp_from_name = serializers.CharField(required=False, allow_blank=True, max_length=180)
    smtp_from_email = serializers.EmailField(required=False, allow_blank=True)

    hermes_enabled = serializers.BooleanField(required=False)
    hermes_webhook_url = serializers.URLField(required=False, allow_blank=True)
    hermes_token = serializers.CharField(
        required=False,
        allow_blank=False,
        write_only=True,
        max_length=2048,
    )
    hermes_default_target = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=180,
    )

    def validate(self, attrs):
        use_tls = attrs.get(
            "smtp_use_tls",
            getattr(self.instance, "smtp_use_tls", True),
        )
        use_ssl = attrs.get(
            "smtp_use_ssl",
            getattr(self.instance, "smtp_use_ssl", False),
        )
        if use_tls and use_ssl:
            raise serializers.ValidationError("SMTP TLS and SSL cannot both be enabled.")
        return attrs


class TestEmailSerializer(NotificationIntegrationSettingsSerializer):
    """Test the draft SMTP fields; never persist them to the integration record."""

    recipient = serializers.EmailField(required=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get("smtp_enabled", False):
            raise serializers.ValidationError(
                {"smtp_enabled": "Enable direct email notifications to run the SMTP test."}
            )
        if not attrs.get("smtp_host"):
            raise serializers.ValidationError({"smtp_host": "SMTP Host is required."})
        if not attrs.get("smtp_from_email"):
            raise serializers.ValidationError({"smtp_from_email": "From Email is required."})
        return attrs


class TestHermesSerializer(serializers.Serializer):
    target = serializers.CharField(required=False, allow_blank=True, max_length=180)
