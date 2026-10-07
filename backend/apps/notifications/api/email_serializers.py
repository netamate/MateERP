from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone
from rest_framework import serializers

from ..email_templates import sanitize_email_html
from ..models import DirectEmailNotification, EmailTemplateStatus


class DirectEmailNotificationSerializer(serializers.ModelSerializer):
    to_recipients = serializers.ListField(
        child=serializers.EmailField(),
        allow_empty=False,
    )
    cc_recipients = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
    )
    bcc_recipients = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
    )
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    template_name = serializers.CharField(source="template.name", read_only=True, allow_null=True)
    action = serializers.ChoiceField(
        choices=["DRAFT", "SCHEDULE", "SEND_NOW"],
        default="DRAFT",
        required=False,
        write_only=True,
    )

    class Meta:
        model = DirectEmailNotification
        fields = [
            "id",
            "legal_entity",
            "to_recipients",
            "cc_recipients",
            "bcc_recipients",
            "template",
            "template_name",
            "template_version",
            "subject",
            "body",
            "html_body",
            "scheduled_for",
            "schedule_timezone",
            "status",
            "attempt_count",
            "last_error",
            "sent_at",
            "template_name",
            "template_version",
            "created_by_email",
            "created_at",
            "updated_at",
            "action",
        ]
        read_only_fields = [
            "id",
            "legal_entity",
            "status",
            "attempt_count",
            "last_error",
            "sent_at",
            "created_by_email",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "scheduled_for": {"required": False, "allow_null": True},
            "schedule_timezone": {"required": False},
        }

    def validate_to_recipients(self, value):
        return self._validate_emails(value, "To")

    def validate_cc_recipients(self, value):
        return self._validate_emails(value, "CC")

    def validate_bcc_recipients(self, value):
        return self._validate_emails(value, "BCC")

    def _validate_emails(self, values, label):
        validator = serializers.EmailField()
        if not isinstance(values, list):
            raise serializers.ValidationError(f"{label} recipients must be a list.")
        cleaned = []
        for value in values:
            email = validator.run_validation(value)
            if email not in cleaned:
                cleaned.append(email)
        return cleaned

    def validate_template(self, value):
        organization = self.context.get("organization")
        entity = self.context.get("legal_entity")
        if value is None:
            return value
        if organization and value.organization_id != organization.id:
            raise serializers.ValidationError("Template belongs to another organization.")
        if value.status != EmailTemplateStatus.ACTIVE:
            raise serializers.ValidationError("Choose an active email template.")
        if value.legal_entity_id and entity and value.legal_entity_id != entity.id:
            raise serializers.ValidationError("Template belongs to a different legal entity.")
        if value.legal_entity_id and entity is None:
            raise serializers.ValidationError(
                "An organization-level direct email cannot use an entity-only template."
            )
        return value

    def validate_html_body(self, value):
        return sanitize_email_html(value)

    def validate_schedule_timezone(self, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise serializers.ValidationError("Use a valid IANA timezone.") from exc
        return value

    def validate(self, attrs):
        action = attrs.get("action", "DRAFT")
        scheduled_for = attrs.get("scheduled_for")
        if action == "SCHEDULE":
            if not scheduled_for:
                raise serializers.ValidationError(
                    {"scheduled_for": "Choose a date and time for a scheduled email."}
                )
            if scheduled_for <= timezone.now():
                raise serializers.ValidationError(
                    {"scheduled_for": "Scheduled time must be in the future."}
                )
        return attrs
