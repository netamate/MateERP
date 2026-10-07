from django.core.management.base import BaseCommand

from ...services import run_due_automations


class Command(BaseCommand):
    help = "Run due MateERP automation policies."

    def handle(self, *args, **options):
        result = run_due_automations()
        self.stdout.write(
            self.style.SUCCESS(
                "Automation run complete: "
                f"{result['executed']} executed, "
                f"{result['failed']} failed, "
                f"{result['skipped']} skipped."
            )
        )
