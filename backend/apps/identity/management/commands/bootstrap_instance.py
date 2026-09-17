import os

from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.identity.models import Organization, User
from apps.identity.services import create_organization_with_owner


class Command(BaseCommand):
    help = "Create the initial MateERP owner, organization, and legal entity idempotently."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--organization", required=True)
        parser.add_argument("--legal-entity")
        parser.add_argument("--display-name")
        parser.add_argument("--timezone", default="UTC")
        parser.add_argument("--base-currency", default="USD")
        parser.add_argument("--django-superuser", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if Organization.objects.exists():
            self.stdout.write(self.style.WARNING("MateERP is already bootstrapped."))
            return

        password = os.environ.get("MATEERP_BOOTSTRAP_PASSWORD")
        if not password:
            raise CommandError("MATEERP_BOOTSTRAP_PASSWORD must be set.")

        email = options["email"].lower()
        display_name = options["display_name"] or email.split("@", 1)[0]
        user, created = User.objects.get_or_create(
            email=email,
            defaults={"display_name": display_name},
        )
        if created:
            validate_password(password, user)
            user.set_password(password)
        elif not user.check_password(password):
            raise CommandError("Existing user password does not match bootstrap credentials.")

        user.display_name = display_name
        if options["django_superuser"]:
            user.is_staff = True
            user.is_superuser = True
        user.save()

        organization, legal_entity, _ = create_organization_with_owner(
            owner=user,
            name=options["organization"],
            legal_entity_name=options["legal_entity"],
            timezone=options["timezone"],
            base_currency=options["base_currency"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Bootstrapped organization {organization.name} "
                f"with legal entity {legal_entity.name}."
            )
        )
