import json
from typing import Any

from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder

from .models import AuditEvent

User = get_user_model()


def record_audit_event(
    *,
    action: str,
    object_type: str,
    object_id: Any,
    actor: User | None = None,
    organization=None,
    legal_entity=None,
    previous_state: dict | None = None,
    new_state: dict | None = None,
    request=None,
) -> AuditEvent:
    ip_address = None
    user_agent = ""
    request_id = ""
    if request is not None:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()
        else:
            ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        request_id = getattr(request, "request_id", "")

    return AuditEvent.objects.create(
        actor=actor,
        organization=organization,
        legal_entity=legal_entity,
        action=action,
        object_type=object_type,
        object_id=str(object_id),
        previous_state=json.loads(json.dumps(previous_state or {}, cls=DjangoJSONEncoder)),
        new_state=json.loads(json.dumps(new_state or {}, cls=DjangoJSONEncoder)),
        ip_address=ip_address or None,
        user_agent=user_agent,
        request_id=request_id,
    )
