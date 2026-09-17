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
        parser.add_argument("--timezone", default="UTC")
        parser.add_argument("--base-currency", default="USD")

    @transaction.atomic
    def handle(self, *args, **options):
        if Organization.objects.exists():
            self.stdout.write(self.style.WARNING("MateERP is already bootstrapped."))
            return

        password = os.environ.get("MATEERP_BOOTSTRAP_PASSWORD")
        if not password:
            raise CommandError("MATEERP_BOOTSTRAP_PASSWORD must be set.")

        user, created = User.objects.get_or_create(
            email=options["email"].lower(),
            defaults={"display_name": options["email"].split("@", 1)[0]},
        )
        if created:
            validate_password(password, user)
            user.set_password(password)
            user.save(update_fields=["password"])
        elif not user.check_password(password):
            raise CommandError("Existing user password does not match bootstrap credentials.")

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
