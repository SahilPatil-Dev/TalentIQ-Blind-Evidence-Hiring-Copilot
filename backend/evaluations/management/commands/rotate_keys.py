from django.core.management.base import BaseCommand

from evaluations.services import keys


class Command(BaseCommand):
    help = "Create a new data key, move all stored identities onto it, and re-wrap data keys."

    def handle(self, *args, **options):
        row = keys.rotate_data_key()
        moved = keys.reencrypt_all()
        wrapped = keys.rewrap_keys()
        self.stdout.write(self.style.SUCCESS(
            f"Active key v{row.version}; re-encrypted {moved} record(s); re-wrapped {wrapped} key(s)."))
