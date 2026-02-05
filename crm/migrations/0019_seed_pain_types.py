# Generated manually to seed PainType options

from django.db import migrations

PAIN_TYPES = [
    ("job_posting", "Job Posting (hiring training role)"),
    ("glassdoor", "Glassdoor/Reviews (training complaints)"),
    ("linkedin_activity", "LinkedIn Activity (discussing challenges)"),
    ("news_press", "News/Press (mentioned in articles)"),
    ("association_member", "Association Member (active in industry groups)"),
    ("compliance_issues", "Compliance Issues (CMS citations, public data)"),
    ("none_found", "None Found"),
]


def seed_pain_types(apps, schema_editor):
    PainType = apps.get_model("crm", "PainType")
    for code, name in PAIN_TYPES:
        PainType.objects.get_or_create(code=code, defaults={"name": name})


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0018_pain_signal_pain_type"),
    ]

    operations = [
        migrations.RunPython(seed_pain_types, noop),
    ]
