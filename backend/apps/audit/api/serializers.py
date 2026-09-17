from rest_framework import serializers

from ..models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True)
    legal_entity_name = serializers.CharField(source="legal_entity.name", read_only=True)

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "actor",
            "actor_email",
            "action",
            "object_type",
            "object_id",
            "previous_state",
            "new_state",
            "ip_address",
            "user_agent",
            "request_id",
            "legal_entity",
            "legal_entity_name",
            "created_at",
        ]
        read_only_fields = fields


class AuditQuerySerializer(serializers.Serializer):
    action = serializers.CharField(required=False, allow_blank=True, max_length=120)
    object_type = serializers.CharField(required=False, allow_blank=True, max_length=120)
    actor_id = serializers.UUIDField(required=False)
    request_id = serializers.CharField(required=False, allow_blank=True, max_length=64)
    search = serializers.CharField(required=False, allow_blank=True, max_length=120)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError("end_date cannot be before start_date.")
        return attrs
