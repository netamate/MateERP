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
