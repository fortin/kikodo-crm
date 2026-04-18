# Generated data migration: seed welcome email steps

from django.db import migrations


def create_welcome_steps(apps, schema_editor):
    WelcomeEmail = apps.get_model("crm", "WelcomeEmail")
    steps = [
        {
            "order": 1,
            "subject": "Welcome!",
            "body": "Hi {{ first_name }},\n\nThanks for subscribing. This is the first email in our welcome series.\n\nReplace this text with your actual welcome content.",
            "offset_hours": 0,
        },
        {
            "order": 2,
            "subject": "Getting started",
            "body": "Hi {{ first_name }},\n\nHere’s the second email in our welcome series (sent 1 hour after signup).\n\nReplace this text with your actual content.",
            "offset_hours": 1,
        },
        {
            "order": 3,
            "subject": "More resources",
            "body": "Hi {{ first_name }},\n\nThird email (3 hours after the previous one).\n\nReplace this text with your actual content.",
            "offset_hours": 3,
        },
        {
            "order": 4,
            "subject": "You’re all set",
            "body": "Hi {{ first_name }},\n\nFinal welcome email (3 hours after the previous one).\n\nReplace this text with your actual content.",
            "offset_hours": 3,
        },
    ]
    for s in steps:
        WelcomeEmail.objects.get_or_create(
            order=s["order"],
            defaults={
                "subject": s["subject"],
                "body": s["body"],
                "offset_hours": s["offset_hours"],
            },
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0034_add_welcome_email_models"),
    ]

    operations = [
        migrations.RunPython(create_welcome_steps, noop),
    ]
