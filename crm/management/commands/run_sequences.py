"""Run due sequence steps, welcome-series emails, one-off scheduled emails (call from cron every 5–15 minutes)."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from crm.models import SequenceEnrollment, WelcomeEmail, WelcomeEnrollment
from crm.utils import advance_sequence_enrollment, send_welcome_email_step


class Command(BaseCommand):
    help = "Process active sequence enrollments, welcome-series enrollments, and one-off scheduled emails whose next run is due."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only list due enrollments and scheduled emails, do not execute.",
        )

    def handle(self, *args, **options):
        now = timezone.now()

        # 1. Process one-off scheduled outbound emails
        from crm.email_utils import process_scheduled_outbound_emails
        from crm.models import Activity

        if options["dry_run"]:
            pending_emails = Activity.objects.filter(
                activity_type="email",
                status="pending",
                due_date__lte=now,
                sequence_step__isnull=True,
                sequence_enrollment__isnull=True,
                contact__email__isnull=False,
                contact__can_email_outbound=True,
            ).exclude(contact__email="")
            email_count = pending_emails.count()
            self.stdout.write(f"Would send {email_count} scheduled email(s).")
        else:
            try:
                sent_count = process_scheduled_outbound_emails(now=now)
                if sent_count:
                    self.stdout.write(self.style.SUCCESS(f"Sent {sent_count} scheduled email(s)."))
            except Exception as e:
                self.stderr.write(f"Error processing scheduled emails: {e}")

        # 2. Process welcome-series enrollments
        welcome_due = WelcomeEnrollment.objects.filter(
            status="active",
            next_send_at__isnull=False,
            next_send_at__lte=now,
        ).select_related("contact")
        welcome_count = welcome_due.count()
        if options["dry_run"]:
            self.stdout.write(f"Would process {welcome_count} welcome enrollment(s).")
            for e in welcome_due[:10]:
                self.stdout.write(f"  Welcome step {e.current_step_index + 1} -> {e.contact}")
            if welcome_count > 10:
                self.stdout.write(f"  ... and {welcome_count - 10} more")
        else:
            welcome_processed = 0
            for enrollment in welcome_due:
                try:
                    welcome_steps = list(
                        WelcomeEmail.objects.filter(
                            automation_id=enrollment.automation_id
                        ).order_by("order")
                    )
                    if enrollment.current_step_index >= len(welcome_steps):
                        enrollment.status = "completed"
                        enrollment.next_send_at = None
                        enrollment.save(update_fields=["status", "next_send_at"])
                        continue
                    step = welcome_steps[enrollment.current_step_index]
                    contact = enrollment.contact
                    if not contact.email or not contact.newsletter_subscribed or not contact.can_marketing_email:
                        enrollment.status = "cancelled"
                        enrollment.next_send_at = None
                        enrollment.save(update_fields=["status", "next_send_at"])
                        continue
                    sent = send_welcome_email_step(contact, step)
                    Activity.objects.create(
                        activity_type="email",
                        direction="outbound",
                        subject=step.subject,
                        description=step.body,
                        contact=contact,
                        status="sent",
                        delivery_status="sent" if sent else "failed",
                        completed_date=now,
                    )
                    enrollment.current_step_index += 1
                    if enrollment.current_step_index >= len(welcome_steps):
                        enrollment.status = "completed"
                        enrollment.next_send_at = None
                    else:
                        next_step = welcome_steps[enrollment.current_step_index]
                        enrollment.next_send_at = now + timedelta(hours=next_step.offset_hours)
                    enrollment.save(update_fields=["current_step_index", "next_send_at", "status"])
                    welcome_processed += 1
                except Exception as e:
                    self.stderr.write(f"Error processing welcome enrollment {enrollment.pk}: {e}")
            if welcome_processed:
                self.stdout.write(self.style.SUCCESS(f"Processed {welcome_processed} welcome email(s)."))

        # 3. Process sequence enrollments
        due = SequenceEnrollment.objects.filter(
            status="active",
            next_run_at__isnull=False,
            next_run_at__lte=now,
        ).select_related("contact", "sequence", "owner")
        count = due.count()
        if options["dry_run"]:
            self.stdout.write(f"Would process {count} sequence enrollment(s).")
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
        self.stdout.write(self.style.SUCCESS(f"Processed {processed} sequence enrollment(s)."))
