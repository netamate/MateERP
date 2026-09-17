from rest_framework import serializers

from apps.identity.models import LegalEntity, Membership, Organization, User
from apps.identity.policy import ROLE_PERMISSIONS


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "display_name", "timezone"]


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "status", "timezone"]


class LegalEntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalEntity
        fields = [
            "id",
            "organization_id",
            "name",
            "slug",
            "status",
            "base_currency",
            "timezone",
            "fiscal_year_start_month",
            "fiscal_year_start_day",
        ]


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    permissions = serializers.SerializerMethodField()
    legal_entity_ids = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = [
            "id",
            "organization_id",
            "user",
            "role",
            "status",
            "all_legal_entities",
            "legal_entity_ids",
            "permissions",
        ]

    def get_permissions(self, obj):
        return sorted(permission.value for permission in ROLE_PERMISSIONS.get(obj.role, frozenset()))

    def get_legal_entity_ids(self, obj):
        if obj.all_legal_entities:
            return []
        return [str(entity.id) for entity in obj.legal_entities.all()]


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class ContextSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    legal_entity_id = serializers.UUIDField(required=False, allow_null=True)


class MembershipRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Membership._meta.get_field("role").choices)


class MembershipScopeSerializer(serializers.Serializer):
    all_legal_entities = serializers.BooleanField()
    legal_entity_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )

    def validate(self, attrs):
        if not attrs["all_legal_entities"] and not attrs["legal_entity_ids"]:
            raise serializers.ValidationError(
                "At least one legal entity is required when all_legal_entities is false."
            )
        return attrs
