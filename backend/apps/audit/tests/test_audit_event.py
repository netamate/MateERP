import uuid
from datetime import date
from decimal import Decimal

import pytest

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit_event


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


@pytest.mark.django_db
def test_audit_event_serializes_uuid_decimal_and_dates_to_json_values():
    reference = uuid.uuid4()
    event = record_audit_event(
        action="test.json_compatible",
        object_type="Subscription",
        object_id=reference,
        previous_state={"vendor": reference},
        new_state={
            "vendor": reference,
            "amount": Decimal("18.00"),
            "next_renewal_date": date(2027, 10, 7),
        },
    )
    event.refresh_from_db()
    assert event.previous_state["vendor"] == str(reference)
    assert event.new_state == {
        "vendor": str(reference),
        "amount": "18.00",
        "next_renewal_date": "2027-10-07",
    }
