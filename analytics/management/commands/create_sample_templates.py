from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from analytics.utils import create_sample_template


class Command(BaseCommand):
    help = "Create sample dashboard templates and metrics"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            default="admin",
            help="Username to create templates for (default: admin)",
        )

    def handle(self, *args, **options):
        username = options["username"]

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User "{username}" does not exist'))
            return

        # Create sample template
        template = create_sample_template(user)

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created sample template "{template.name}" '
                f'with {template.metrics.count()} metrics for user "{username}"'
            )
        )

        # Show template details
        self.stdout.write(f"\nTemplate ID: {template.id}")
        self.stdout.write(f"Template Name: {template.name}")
        self.stdout.write(f"Period Type: {template.period_type}")
        self.stdout.write(f"Metrics Count: {template.metrics.count()}")

        # Show first few metrics
        self.stdout.write("\nFirst 5 metrics:")
        for metric in template.metrics.all()[:5]:
            self.stdout.write(
                f"  - {metric.metric_name} ({metric.period}): "
                f"Target: {metric.target_value}, Actual: {metric.actual_value}"
            )
