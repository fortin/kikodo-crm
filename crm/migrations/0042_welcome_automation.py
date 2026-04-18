# Generated manually: parent WelcomeAutomation + FK on steps and enrollments

import django.db.models.deletion
from django.db import migrations, models


def create_default_and_link_steps(apps, schema_editor):
    WelcomeAutomation = apps.get_model("crm", "WelcomeAutomation")
    WelcomeEmail = apps.get_model("crm", "WelcomeEmail")
    default, _ = WelcomeAutomation.objects.get_or_create(
        slug="default",
        defaults={
            "name": "Default welcome series",
            "is_active": True,
            "enrollment_weight": 1,
        },
    )
    WelcomeEmail.objects.filter(automation__isnull=True).update(automation_id=default.pk)


def link_enrollments_to_default(apps, schema_editor):
    WelcomeAutomation = apps.get_model("crm", "WelcomeAutomation")
    WelcomeEnrollment = apps.get_model("crm", "WelcomeEnrollment")
    default = WelcomeAutomation.objects.get(slug="default")
    WelcomeEnrollment.objects.filter(automation__isnull=True).update(automation_id=default.pk)


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0041_add_newsletter_issue_preheader"),
    ]

    operations = [
        migrations.CreateModel(
            name="WelcomeAutomation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                (
                    "slug",
                    models.SlugField(
                        help_text="Stable id; auto-generated from name when left blank.",
                        max_length=64,
                        unique=True,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Inactive automations are not assigned to new subscribers.",
                    ),
                ),
                (
                    "enrollment_weight",
                    models.PositiveIntegerField(
                        default=1,
                        help_text="Relative chance this automation is chosen among active ones (e.g. 1 and 1 → 50/50).",
                    ),
                ),
            ],
            options={
                "verbose_name": "Welcome automation",
                "verbose_name_plural": "Welcome automations",
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="welcomeemail",
            name="automation",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="steps",
                to="crm.welcomeautomation",
            ),
        ),
        migrations.RunPython(create_default_and_link_steps, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="welcomeemail",
            name="order",
            field=models.PositiveIntegerField(
                help_text="Step order (1 = first at signup; then offset_hours after each prior send)",
            ),
        ),
        migrations.AddConstraint(
            model_name="welcomeemail",
            constraint=models.UniqueConstraint(
                fields=("automation", "order"),
                name="crm_welcomeemail_automation_order_uniq",
            ),
        ),
        migrations.AlterField(
            model_name="welcomeemail",
            name="automation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="steps",
                to="crm.welcomeautomation",
            ),
        ),
        migrations.AddField(
            model_name="welcomeenrollment",
            name="automation",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="enrollments",
                to="crm.welcomeautomation",
            ),
        ),
        migrations.RunPython(link_enrollments_to_default, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="welcomeenrollment",
            name="automation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="enrollments",
                to="crm.welcomeautomation",
            ),
        ),
    ]
