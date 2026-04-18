"""Send newsletter editions that are due (scheduled_date <= today, not yet sent)."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from crm.email_utils import send_newsletter_edition_to_contact
from crm.models import Activity, Contact, NewsletterEdition


class Command(BaseCommand):
    help = "Find newsletter editions due today or in the past that have not been sent; send to subscribed contacts and set sent_at."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only list due editions and subscriber counts, do not send.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        today = now.date()

        due_editions = NewsletterEdition.objects.filter(
            status="scheduled",
            sent_at__isnull=True,
        ).select_related("plan", "owner")

        due_list = []
        for edition in due_editions:
            sd = edition.scheduled_date
            if sd is None or sd > today:
                continue
            due_list.append(edition)

        if not due_list:
            self.stdout.write("No newsletter editions due to send.")
            return

        subscribers = Contact.objects.filter(
            newsletter_subscribed=True,
            can_marketing_email=True,
        ).exclude(email__isnull=True).exclude(email="")

        if options["dry_run"]:
            for edition in due_list:
                count = subscribers.count()
                self.stdout.write(
                    f"Would send edition {edition} (scheduled {edition.scheduled_date}) to {count} subscriber(s)."
                )
            return

        sent_total = 0
        for edition in due_list:
            sent_count = 0
            for contact in subscribers:
                try:
                    ok = send_newsletter_edition_to_contact(contact, edition)
                    if ok:
                        Activity.objects.create(
                            activity_type="email",
                            direction="outbound",
                            subject=edition.subject or edition.weekly_theme or "Newsletter",
                            description=edition.body_html,
                            contact=contact,
                            company=contact.company,
                            owner=edition.owner,
                            status="sent",
                            delivery_status="sent",
                            completed_date=now,
                        )
                        sent_count += 1
                except Exception as e:
                    self.stderr.write(f"Error sending to {contact.email} for edition {edition.pk}: {e}")
            edition.sent_at = now
            edition.save(update_fields=["sent_at"])
            sent_total += sent_count
            self.stdout.write(
                self.style.SUCCESS(f"Sent edition {edition} to {sent_count} subscriber(s).")
            )
        if sent_total:
            self.stdout.write(self.style.SUCCESS(f"Total: {sent_total} newsletter email(s) sent."))
