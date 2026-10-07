from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone
from rest_framework import serializers

from ..models import DirectEmailNotification


class DirectEmailNotificationSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
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
            "subject",
            "body",
            "scheduled_for",
            "schedule_timezone",
            "status",
            "attempt_count",
            "last_error",
            "sent_at",
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
            "to_recipients": {"allow_empty": False},
            "cc_recipients": {"required": False},
            "bcc_recipients": {"required": False},
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
