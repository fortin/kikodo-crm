from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0042_welcome_automation"),
    ]

    operations = [
        migrations.AlterField(
            model_name="welcomeautomation",
            name="slug",
            field=models.SlugField(
                blank=True,
                help_text="Stable id; auto-generated from name when left blank.",
                max_length=64,
                unique=True,
            ),
        ),
    ]
