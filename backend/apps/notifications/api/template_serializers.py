import re

from rest_framework import serializers

from ..email_templates import variable_catalog, validate_template_variables
from ..models import EmailTemplate, EmailTemplateVersion, NotificationKind

KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,118}[a-z0-9]$|^[a-z0-9]$")


class EmailTemplateVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplateVersion
        fields = [
            "id",
            "version_number",
            "name",
            "description",
            "signal",
            "subject_template",
            "html_body_template",
            "text_body_template",
            "created_at",
        ]
        read_only_fields = fields


class EmailTemplateSerializer(serializers.ModelSerializer):
    legal_entity_name = serializers.CharField(
        source="legal_entity.name",
        read_only=True,
        allow_null=True,
    )
    created_by_email = serializers.EmailField(
        source="created_by.email",
        read_only=True,
        allow_null=True,
    )
    updated_by_email = serializers.EmailField(
        source="updated_by.email",
        read_only=True,
        allow_null=True,
    )
    available_variables = serializers.SerializerMethodField()
    version_count = serializers.IntegerField(source="versions.count", read_only=True)

    class Meta:
        model = EmailTemplate
        exclude = ["organization"]
        read_only_fields = [
            "id",
            "current_version",
            "is_system_default",
            "created_at",
            "updated_at",
            "legal_entity_name",
            "created_by_email",
            "updated_by_email",
            "available_variables",
            "version_count",
        ]

    def get_available_variables(self, obj):
        return variable_catalog(obj.signal)

    def validate_template_key(self, value):
        value = value.strip().lower()
        if not KEY_RE.fullmatch(value):
            raise serializers.ValidationError(
                "Use lowercase letters, numbers and hyphens only."
            )
        return value

    def validate(self, attrs):
        organization = self.context.get("organization")
        entity = attrs.get("legal_entity", getattr(self.instance, "legal_entity", None))
        if entity and organization and entity.organization_id != organization.id:
            raise serializers.ValidationError(
                {"legal_entity": "Choose a legal entity from this organization."}
            )
        signal = attrs.get("signal", getattr(self.instance, "signal", None))
        supported = {
            None,
            NotificationKind.RENEWAL_DUE,
            NotificationKind.BUDGET_THRESHOLD,
            NotificationKind.MISSING_INVOICE,
            NotificationKind.INVOICE_OVERDUE,
            NotificationKind.RECONCILIATION_NEEDED,
        }
        if signal not in supported:
            raise serializers.ValidationError(
                {"signal": "This notification signal is not supported by the designer."}
            )
        subject = attrs.get(
            "subject_template",
            getattr(self.instance, "subject_template", ""),
        )
        text_body = attrs.get(
            "text_body_template",
            getattr(self.instance, "text_body_template", ""),
        )
        html_body = attrs.get(
            "html_body_template",
            getattr(self.instance, "html_body_template", ""),
        )
        try:
            validate_template_variables(
                signal=signal,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
            )
        except Exception as exc:
            raise serializers.ValidationError({"template": str(exc)}) from exc

        key = attrs.get("template_key", getattr(self.instance, "template_key", ""))
        duplicates = EmailTemplate.objects.filter(
            organization=organization,
            template_key=key,
        )
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if key and duplicates.exists():
            raise serializers.ValidationError(
                {"template_key": "This template key already exists."}
            )
        return attrs


class EmailTemplatePreviewSerializer(serializers.Serializer):
    signal = serializers.ChoiceField(
        choices=[
            NotificationKind.RENEWAL_DUE,
            NotificationKind.BUDGET_THRESHOLD,
            NotificationKind.MISSING_INVOICE,
            NotificationKind.INVOICE_OVERDUE,
            NotificationKind.RECONCILIATION_NEEDED,
        ],
        required=False,
        allow_null=True,
    )
    subject_template = serializers.CharField(max_length=255)
    text_body_template = serializers.CharField()
    html_body_template = serializers.CharField(required=False, allow_blank=True)
    context = serializers.JSONField(required=False, default=dict)


class EmailTemplateTestSerializer(EmailTemplatePreviewSerializer):
    recipient = serializers.EmailField()
