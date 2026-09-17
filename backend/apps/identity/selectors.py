from uuid import UUID

from django.db.models import QuerySet

from .models import LegalEntity, Membership, MembershipStatus, Organization, User


def memberships_for_user(user: User) -> QuerySet[Membership]:
    return (
        Membership.objects.filter(user=user, status=MembershipStatus.ACTIVE)
        .select_related("organization")
        .prefetch_related("legal_entities")
    )


def membership_for_user(user: User, organization_id: UUID | str) -> Membership | None:
    return (
        Membership.objects.filter(
            user=user,
            organization_id=organization_id,
            status=MembershipStatus.ACTIVE,
        )
        .select_related("organization")
        .first()
    )


def accessible_legal_entities(membership: Membership) -> QuerySet[LegalEntity]:
    base = LegalEntity.objects.filter(
        organization=membership.organization,
        status="ACTIVE",
    )
    if membership.all_legal_entities:
        return base
    return base.filter(scoped_memberships=membership).distinct()


def organization_for_user(user: User, organization_id: UUID | str) -> Organization | None:
    membership = membership_for_user(user, organization_id)
    return membership.organization if membership else None
