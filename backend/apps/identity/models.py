import uuid

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .managers import UserManager


class RecordStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    ARCHIVED = "ARCHIVED", "Archived"


class MembershipStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"


class Role(models.TextChoices):
    OWNER = "OWNER", "Owner"
    ADMINISTRATOR = "ADMINISTRATOR", "Administrator"
    FINANCE_MANAGER = "FINANCE_MANAGER", "Finance Manager"
    APPROVER = "APPROVER", "Approver"
    MEMBER = "MEMBER", "Member"
    VIEWER = "VIEWER", "Viewer"


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=160, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return self.display_name or self.email


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=120, unique=True)
    status = models.CharField(
        max_length=16, choices=RecordStatus.choices, default=RecordStatus.ACTIVE
    )
    timezone = models.CharField(max_length=64, default="UTC")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class LegalEntity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="legal_entities"
    )
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=120)
    status = models.CharField(
        max_length=16, choices=RecordStatus.choices, default=RecordStatus.ACTIVE
    )
    base_currency = models.CharField(max_length=3, default="USD")
    timezone = models.CharField(max_length=64, default="UTC")
    fiscal_year_start_month = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    fiscal_year_start_day = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"], name="uniq_legal_entity_slug_per_org"
            )
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.base_currency = self.base_currency.upper()
        super().save(*args, **kwargs)


class Membership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="memberships"
    )
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="memberships")
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.MEMBER)
    status = models.CharField(
        max_length=16, choices=MembershipStatus.choices, default=MembershipStatus.ACTIVE
    )
    all_legal_entities = models.BooleanField(default=False)
    legal_entities = models.ManyToManyField(
        LegalEntity,
        through="MembershipLegalEntityScope",
        related_name="scoped_memberships",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__email"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"], name="uniq_membership_per_org_user"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.email} @ {self.organization.name}"


class MembershipLegalEntityScope(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    membership = models.ForeignKey(
        Membership, on_delete=models.CASCADE, related_name="legal_entity_scopes"
    )
    legal_entity = models.ForeignKey(
        LegalEntity, on_delete=models.PROTECT, related_name="membership_scopes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "legal_entity"], name="uniq_membership_legal_entity_scope"
            )
        ]

    def __str__(self) -> str:
        return f"{self.membership} -> {self.legal_entity}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError

        if (
            self.membership_id
            and self.legal_entity_id
            and self.membership.organization_id != self.legal_entity.organization_id
        ):
            raise ValidationError("Legal entity must belong to the membership organization.")
