import django.core.validators
from django.db import migrations, models


def seed_report_group_coefficients(apps, schema_editor):
    ReportGroup = apps.get_model("timetable", "ReportGroup")
    ReportGroup.objects.filter(kind="course").update(coefficient="1.00")
    ReportGroup.objects.filter(kind="self_study").update(coefficient="0.50")


class Migration(migrations.Migration):

    dependencies = [
        ("timetable", "0006_export_parameters"),
    ]

    operations = [
        migrations.AddField(
            model_name="reportgroup",
            name="coefficient",
            field=models.DecimalField(
                decimal_places=2,
                default=1,
                help_text="导出时预填的基础系数",
                max_digits=4,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.RunPython(
            seed_report_group_coefficients, migrations.RunPython.noop
        ),
    ]
