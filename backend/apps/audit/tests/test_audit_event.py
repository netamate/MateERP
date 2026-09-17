import pytest

from apps.audit.models import AuditEvent


@pytest.mark.django_db
def test_audit_event_is_append_only():
    event = AuditEvent.objects.create(
        action="test.created",
        object_type="Test",
        object_id="123",
    )
    event.action = "test.changed"

    with pytest.raises(TypeError):
        event.save()

    with pytest.raises(TypeError):
        event.delete()

    with pytest.raises(TypeError):
        AuditEvent.objects.filter(pk=event.pk).update(action="test.changed")
