from rest_framework import serializers

from ..models import Notification


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
