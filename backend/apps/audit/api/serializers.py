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
