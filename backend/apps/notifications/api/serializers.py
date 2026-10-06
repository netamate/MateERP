from rest_framework import serializers

from ..models import Notification, NotificationDelivery


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "kind",
            "severity",
            "title",
            "message",
            "link",
            "due_date",
            "read_at",
            "resolved_at",
            "created_at",
        ]
        read_only_fields = fields


class NotificationDeliverySerializer(serializers.ModelSerializer):
    subscription_name = serializers.CharField(source="subscription.name", read_only=True)

    class Meta:
        model = NotificationDelivery
        fields = [
            "id",
            "subscription",
            "subscription_name",
            "channel",
            "destination",
            "reminder_days_before",
            "due_date",
            "title",
            "message",
            "status",
            "attempt_count",
            "last_error",
            "sent_at",
            "created_at",
        ]
        read_only_fields = fields



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
            raise serializers.ValidationError(
                "SMTP TLS and SSL cannot both be enabled."
            )
        return attrs


class TestEmailSerializer(serializers.Serializer):
    recipient = serializers.EmailField()


class TestHermesSerializer(serializers.Serializer):
    target = serializers.CharField(required=False, allow_blank=True, max_length=180)
