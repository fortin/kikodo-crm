"""Delete (hard delete) duplicate contacts where first+last name match and job_title is empty."""

from collections import defaultdict

from django.core.management.base import BaseCommand

from crm.models import Contact


def normalized_full_name(contact):
    """Same person = same normalized full name, regardless of first/last split."""
    first = (contact.first_name or "").strip()
    last = (contact.last_name or "").strip()
    return " ".join((first + " " + last).split()).lower()


class Command(BaseCommand):
    help = (
        "Finds contacts that share the same first and last name as another contact, "
        "and permanently deletes the one(s) whose Job Title is empty. Keeps records that have a job title."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report what would be deleted, do not delete.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print counts of contacts, duplicate name groups, and empty-title dupes.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Include inactive (archived) contacts when finding duplicates. Default: active only.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]
        use_active_only = not options["all"]
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN – no records will be deleted."))

        base = Contact.objects.filter(is_active=True) if use_active_only else Contact.objects
        contacts_qs = base.only("id", "first_name", "last_name", "job_title").order_by("id")

        # Group by normalized full name so "Alex A."+"Bran" and "Alex"+"A. Bran" match
        by_name = defaultdict(list)
        for c in contacts_qs:
            by_name[normalized_full_name(c)].append(c)

        total = sum(len(g) for g in by_name.values())
        dupe_groups = sum(1 for k, g in by_name.items() if k and len(g) > 1)
        groups_with_empty = [(k, g) for k, g in by_name.items() if k and len(g) > 1 and any(not (c.job_title or "").strip() for c in g)]
        if verbose or not groups_with_empty:
            self.stdout.write(
                f"Checked {total} contact(s), {dupe_groups} duplicate-name group(s), "
                f"{len(groups_with_empty)} group(s) with at least one empty job title."
            )

        total_deleted = 0
        for key, candidates in by_name.items():
            if not key or len(candidates) <= 1:
                continue
            to_delete = [c for c in candidates if not (c.job_title or "").strip()]
            for c in to_delete:
                self.stdout.write(
                    f"  {'Would delete' if dry_run else 'Deleting'}: id={c.pk} "
                    f"{c.first_name or ''} {c.last_name or ''} (job_title empty)"
                )
                if not dry_run:
                    c.delete()
                    total_deleted += 1
                else:
                    total_deleted += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"Dry run: {total_deleted} record(s) would be deleted.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Deleted {total_deleted} duplicate contact(s) with empty job title.")
            )
