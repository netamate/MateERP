import django.contrib.auth.models
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models

import apps.identity.managers


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="Organization",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("ARCHIVED", "Archived")], default="ACTIVE", max_length=16)),
                ("timezone", models.CharField(default="UTC", max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="User",
            fields=[
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False, help_text="Designates that this user has all permissions without explicitly assigning them.", verbose_name="superuser status")),
                ("first_name", models.CharField(blank=True, max_length=150, verbose_name="first name")),
                ("last_name", models.CharField(blank=True, max_length=150, verbose_name="last name")),
                ("is_staff", models.BooleanField(default=False, help_text="Designates whether the user can log into this admin site.", verbose_name="staff status")),
                ("is_active", models.BooleanField(default=True, help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.", verbose_name="active")),
                ("date_joined", models.DateTimeField(default=django.utils.timezone.now, verbose_name="date joined")),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("display_name", models.CharField(blank=True, max_length=160)),
                ("timezone", models.CharField(default="UTC", max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("groups", models.ManyToManyField(blank=True, help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.", related_name="user_set", related_query_name="user", to="auth.group", verbose_name="groups")),
                ("user_permissions", models.ManyToManyField(blank=True, help_text="Specific permissions for this user.", related_name="user_set", related_query_name="user", to="auth.permission", verbose_name="user permissions")),
            ],
            options={"verbose_name": "user", "verbose_name_plural": "users"},
            managers=[("objects", apps.identity.managers.UserManager())],
        ),
        migrations.CreateModel(
            name="LegalEntity",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("slug", models.SlugField(max_length=120)),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("ARCHIVED", "Archived")], default="ACTIVE", max_length=16)),
                ("base_currency", models.CharField(default="USD", max_length=3)),
                ("timezone", models.CharField(default="UTC", max_length=64)),
                ("fiscal_year_start_month", models.PositiveSmallIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(12)])),
                ("fiscal_year_start_day", models.PositiveSmallIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(31)])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="legal_entities", to="identity.organization")),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Membership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("role", models.CharField(choices=[("OWNER", "Owner"), ("ADMINISTRATOR", "Administrator"), ("FINANCE_MANAGER", "Finance Manager"), ("APPROVER", "Approver"), ("MEMBER", "Member"), ("VIEWER", "Viewer")], default="MEMBER", max_length=32)),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("SUSPENDED", "Suspended")], default="ACTIVE", max_length=16)),
                ("all_legal_entities", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="memberships", to="identity.organization")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="memberships", to="identity.user")),
            ],
            options={"ordering": ["user__email"]},
        ),
        migrations.CreateModel(
            name="MembershipLegalEntityScope",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("legal_entity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="membership_scopes", to="identity.legalentity")),
                ("membership", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="legal_entity_scopes", to="identity.membership")),
            ],
        ),
        migrations.AddField(
            model_name="membership",
            name="legal_entities",
            field=models.ManyToManyField(blank=True, related_name="scoped_memberships", through="identity.MembershipLegalEntityScope", to="identity.legalentity"),
        ),
        migrations.AddConstraint(
            model_name="legalentity",
            constraint=models.UniqueConstraint(fields=("organization", "slug"), name="uniq_legal_entity_slug_per_org"),
        ),
        migrations.AddConstraint(
            model_name="membership",
            constraint=models.UniqueConstraint(fields=("organization", "user"), name="uniq_membership_per_org_user"),
        ),
        migrations.AddConstraint(
            model_name="membershiplegalentityscope",
            constraint=models.UniqueConstraint(fields=("membership", "legal_entity"), name="uniq_membership_legal_entity_scope"),
        ),
    ]
