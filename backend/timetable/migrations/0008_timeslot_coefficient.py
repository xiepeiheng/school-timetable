import django.core.validators
from django.db import migrations, models

SLOT_COEFFICIENTS = {
    "早读": "0.500",
    "一": "1.000",
    "二": "1.000",
    "三": "1.000",
    "四": "1.200",
    "五": "1.000",
    "六": "1.000",
    "七": "1.000",
    "八": "1.200",
    "晚一": "0.500",
    "晚二": "0.500",
    "晚三": "0.500",
}


def seed_timeslot_coefficients(apps, schema_editor):
    TimeSlot = apps.get_model("timetable", "TimeSlot")
    for slot in TimeSlot.objects.all():
        slot.coefficient = SLOT_COEFFICIENTS.get(slot.name, "1.000")
        slot.save(update_fields=["coefficient"])


class Migration(migrations.Migration):

    dependencies = [
        ("timetable", "0007_reportgroup_coefficient"),
    ]

    operations = [
        migrations.AddField(
            model_name="timeslot",
            name="coefficient",
            field=models.DecimalField(
                decimal_places=3,
                default=1,
                help_text="该节次的固有基准系数",
                max_digits=4,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.RunPython(
            seed_timeslot_coefficients, migrations.RunPython.noop
        ),
        migrations.RemoveField(
            model_name="reportgroup",
            name="coefficient",
        ),
    ]
