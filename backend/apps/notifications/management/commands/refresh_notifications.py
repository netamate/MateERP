from django.core.management.base import BaseCommand

from ...services import run_alert_rules


class Command(BaseCommand):
    help = "Evaluate scheduled MateERP alert rules and deliver idempotent notifications."

    def add_arguments(self, parser):
        parser.add_argument(
            "--horizon-days",
            type=int,
            default=365,
            help="Compatibility option retained for existing deployment commands.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Evaluate enabled rules immediately, ignoring their schedule.",
        )

    def handle(self, *args, **options):
        horizon_days = options["horizon_days"]
        if horizon_days < 0 or horizon_days > 365:
            raise ValueError("--horizon-days must be between 0 and 365.")

        result = run_alert_rules(force=options["force"])
        self.stdout.write(
            self.style.SUCCESS(
                "Alert refresh complete: "
                f"{result['rules_evaluated']} rules evaluated, "
                f"{result['active_events']} active events, "
                f"{result['deliveries_sent']} sent, "
                f"{result['deliveries_failed']} failed, "
                f"{result['rules_skipped']} skipped."
            )
        )
