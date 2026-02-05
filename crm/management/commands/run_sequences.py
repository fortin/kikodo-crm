"""Run due sequence steps (call from cron every 5–15 minutes)."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from crm.models import SequenceEnrollment
from crm.utils import advance_sequence_enrollment


class Command(BaseCommand):
    help = "Process active sequence enrollments whose next_run_at is due; send emails and create tasks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only list due enrollments, do not execute.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        due = SequenceEnrollment.objects.filter(
            status="active",
            next_run_at__isnull=False,
            next_run_at__lte=now,
        ).select_related("contact", "sequence", "owner")
        count = due.count()
        if options["dry_run"]:
            self.stdout.write(f"Would process {count} due enrollment(s).")
            for e in due[:10]:
                self.stdout.write(f"  {e.sequence.name} -> {e.contact}")
            if count > 10:
                self.stdout.write(f"  ... and {count - 10} more")
            return
        processed = 0
        for enrollment in due:
            try:
                activity = advance_sequence_enrollment(enrollment, now=now)
                if activity:
                    processed += 1
            except Exception as e:
                self.stderr.write(f"Error processing enrollment {enrollment.pk}: {e}")
        self.stdout.write(self.style.SUCCESS(f"Processed {processed} enrollment(s)."))
