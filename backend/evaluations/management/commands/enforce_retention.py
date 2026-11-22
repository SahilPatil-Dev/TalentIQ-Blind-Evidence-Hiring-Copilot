from django.core.management.base import BaseCommand

from evaluations.services import retention


class Command(BaseCommand):
    help = "Delete candidate data that is past the retention policy (use --dry-run to preview)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        result = retention.enforce(dry_run=options["dry_run"])
        verb = "would delete" if options["dry_run"] else "deleted"
        self.stdout.write(self.style.SUCCESS(f"Retention: {verb} {result['due']} application(s)."))
