from django.db import migrations

GROUPS = [
    ("early_read", 0),
    ("morning", 1),
    ("afternoon", 2),
    ("self_study", 3),
]

MORNING = {"一", "二", "三", "四"}
AFTERNOON = {"五", "六", "七", "八"}
SELF_STUDY = {"晚一", "晚二", "晚三"}


def _kind_for(name):
    if name == "早读":
        return "early_read"
    if name in MORNING:
        return "morning"
    if name in AFTERNOON:
        return "afternoon"
    if name in SELF_STUDY:
        return "self_study"
    return None


def seed(apps, schema_editor):
    ReportGroup = apps.get_model("timetable", "ReportGroup")
    TimeSlot = apps.get_model("timetable", "TimeSlot")

    groups = {}
    for kind, order in GROUPS:
        group, _ = ReportGroup.objects.get_or_create(
            kind=kind, defaults={"sort_order": order}
        )
        groups[kind] = group

    for slot in TimeSlot.objects.all():
        kind = _kind_for(slot.name)
        if kind and slot.report_group_id != groups[kind].id:
            slot.report_group = groups[kind]
            slot.save(update_fields=["report_group"])


def unseed(apps, schema_editor):
    ReportGroup = apps.get_model("timetable", "ReportGroup")
    TimeSlot = apps.get_model("timetable", "TimeSlot")
    TimeSlot.objects.update(report_group=None)
    ReportGroup.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("timetable", "0003_reportgroup_timeslot_report_group"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
