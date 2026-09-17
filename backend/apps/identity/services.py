from dataclasses import dataclass
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils.text import slugify

from apps.audit.services import record_audit_event

from .models import LegalEntity, Membership, MembershipLegalEntityScope, Organization, Role, User
from .policy import Permission, has_permission
from .selectors import accessible_legal_entities, membership_for_user


@dataclass(frozen=True)
class ActiveContext:
    membership: Membership
    legal_entity: LegalEntity | None


@transaction.atomic
def create_organization_with_owner(
    *,
    owner: User,
    name: str,
    slug: str | None = None,
    timezone: str = "UTC",
    legal_entity_name: str | None = None,
    base_currency: str = "USD",
) -> tuple[Organization, LegalEntity, Membership]:
    organization = Organization.objects.create(
        name=name,
        slug=slug or slugify(name),
        timezone=timezone,
    )
    legal_entity = LegalEntity.objects.create(
        organization=organization,
        name=legal_entity_name or name,
        slug=slugify(legal_entity_name or name),
        timezone=timezone,
        base_currency=base_currency.upper(),
    )
    membership = Membership.objects.create(
        organization=organization,
        user=owner,
        role=Role.OWNER,
        all_legal_entities=True,
    )
    record_audit_event(
        actor=owner,
        organization=organization,
        legal_entity=legal_entity,
        action="organization.created",
        object_type="Organization",
        object_id=organization.id,
        new_state={"name": organization.name, "slug": organization.slug},
    )
    return organization, legal_entity, membership


@transaction.atomic
def set_active_context(
    *,
    user: User,
    organization_id: UUID | str,
    legal_entity_id: UUID | str | None,
) -> ActiveContext:
    membership = membership_for_user(user, organization_id)
    if membership is None:
        raise PermissionDenied("You do not have access to this organization.")

    legal_entity = None
    if legal_entity_id:
        legal_entity = accessible_legal_entities(membership).filter(id=legal_entity_id).first()
        if legal_entity is None:
            raise PermissionDenied("You do not have access to this legal entity.")

    return ActiveContext(membership=membership, legal_entity=legal_entity)


@transaction.atomic
def change_membership_role(
    *,
    actor_membership: Membership,
    membership: Membership,
    role: str,
) -> Membership:
    if not has_permission(actor_membership, Permission.MANAGE_MEMBERS):
        raise PermissionDenied("You do not have permission to manage members.")
    if actor_membership.organization_id != membership.organization_id:
        raise PermissionDenied("Cross-organization membership changes are not allowed.")
    if role == Role.OWNER and actor_membership.role != Role.OWNER:
        raise PermissionDenied("Only an owner can grant the owner role.")
    if membership.role == Role.OWNER and actor_membership.role != Role.OWNER:
        raise PermissionDenied("Only an owner can change another owner's role.")
    if membership.role == Role.OWNER and role != Role.OWNER:
        owner_count = Membership.objects.filter(
            organization=membership.organization,
            role=Role.OWNER,
            status="ACTIVE",
        ).count()
        if owner_count <= 1:
            raise ValidationError("An organization must retain at least one active owner.")

    previous = {"role": membership.role}
    membership.role = role
    membership.full_clean()
    membership.save(update_fields=["role", "updated_at"])
    record_audit_event(
        actor=actor_membership.user,
        organization=membership.organization,
        action="membership.role_changed",
        object_type="Membership",
        object_id=membership.id,
        previous_state=previous,
        new_state={"role": membership.role},
    )
    return membership


@transaction.atomic
def set_membership_legal_entity_scope(
    *,
    actor_membership: Membership,
    membership: Membership,
    all_legal_entities: bool,
    legal_entity_ids: list[UUID | str],
) -> Membership:
    if not has_permission(actor_membership, Permission.MANAGE_MEMBERS):
        raise PermissionDenied("You do not have permission to manage members.")
    if actor_membership.organization_id != membership.organization_id:
        raise PermissionDenied("Cross-organization membership changes are not allowed.")
    if membership.role == Role.OWNER and actor_membership.role != Role.OWNER:
        raise PermissionDenied("Only an owner can change another owner's scope.")

    entities = list(
        LegalEntity.objects.filter(
            organization=membership.organization,
            id__in=legal_entity_ids,
            status="ACTIVE",
        )
    )
    if not all_legal_entities and len(entities) != len(set(map(str, legal_entity_ids))):
        raise ValidationError("One or more legal entities are invalid for this organization.")

    membership.all_legal_entities = all_legal_entities
    membership.save(update_fields=["all_legal_entities", "updated_at"])
    membership.legal_entity_scopes.all().delete()
    if not all_legal_entities:
        MembershipLegalEntityScope.objects.bulk_create(
            [
                MembershipLegalEntityScope(membership=membership, legal_entity=entity)
                for entity in entities
            ]
        )

    record_audit_event(
        actor=actor_membership.user,
        organization=membership.organization,
        action="membership.scope_changed",
        object_type="Membership",
        object_id=membership.id,
        new_state={
            "all_legal_entities": all_legal_entities,
            "legal_entity_ids": [str(entity.id) for entity in entities],
        },
    )
    return membership
