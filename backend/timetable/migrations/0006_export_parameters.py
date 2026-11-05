import django.core.validators
from django.db import migrations, models


def seed_export_parameters(apps, schema_editor):
    ReportGroup = apps.get_model("timetable", "ReportGroup")
    TimeSlot = apps.get_model("timetable", "TimeSlot")
    CourseSession = apps.get_model("timetable", "CourseSession")
    TemplateEntry = apps.get_model("timetable", "TemplateEntry")
    SchoolClass = apps.get_model("timetable", "SchoolClass")
    Subject = apps.get_model("timetable", "Subject")
    Teacher = apps.get_model("timetable", "Teacher")

    course, _ = ReportGroup.objects.get_or_create(
        kind="course", defaults={"sort_order": 0}
    )
    course.sort_order = 0
    course.save(update_fields=["sort_order"])
    study, _ = ReportGroup.objects.get_or_create(
        kind="self_study", defaults={"sort_order": 1}
    )
    study.sort_order = 1
    study.save(update_fields=["sort_order"])

    course_names = {"一", "二", "三", "四", "五", "六", "七", "八"}
    study_names = {"早读", "晚一", "晚二", "晚三"}
    for slot in TimeSlot.objects.all():
        if slot.name in course_names:
            slot.report_group_id = course.id
            slot.save(update_fields=["report_group"])
        elif slot.name in study_names:
            slot.report_group_id = study.id
            slot.save(update_fields=["report_group"])
        elif slot.name == "晚四":
            in_use = (
                CourseSession.objects.filter(time_slot_id=slot.id).exists()
                or TemplateEntry.objects.filter(time_slot_id=slot.id).exists()
            )
            if in_use:
                slot.is_active = False
                slot.report_group_id = None
                slot.save(update_fields=["is_active", "report_group"])
            else:
                slot.delete()
        elif slot.report_group_id is not None:
            slot.report_group_id = None
            slot.save(update_fields=["report_group"])

    ReportGroup.objects.exclude(kind__in=["course", "self_study"]).delete()

    SchoolClass.objects.filter(name__in=["2601", "2602"]).update(
        is_key_class=True
    )
    Subject.objects.filter(name__in=["音乐", "体育", "美术", "舞蹈"]).update(
        is_main=False
    )
    Teacher.objects.filter(name="陈海燕").update(is_cross_grade=True)
    Teacher.objects.filter(
        subject__name__in=["音乐", "体育", "美术", "舞蹈"]
    ).update(full_load_score=14)
    Teacher.objects.exclude(
        subject__name__in=["音乐", "体育", "美术", "舞蹈"]
    ).update(full_load_score=12)


class Migration(migrations.Migration):

    dependencies = [
        ("timetable", "0005_alter_coursesession_flag"),
    ]

    operations = [
        migrations.AddField(
            model_name="subject",
            name="is_main",
            field=models.BooleanField(
                default=True,
                help_text="正课；音乐/体育/美术/舞蹈等为副科",
            ),
        ),
        migrations.AddField(
            model_name="teacher",
            name="is_cross_grade",
            field=models.BooleanField(
                default=False, help_text="跨年级教师系数 1.2"
            ),
        ),
        migrations.AddField(
            model_name="teacher",
            name="full_load_score",
            field=models.PositiveSmallIntegerField(
                default=12,
                help_text="每周满课系数",
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
        migrations.AddField(
            model_name="schoolclass",
            name="is_key_class",
            field=models.BooleanField(
                default=False, help_text="凌云班/重点班"
            ),
        ),
        migrations.AlterField(
            model_name="reportgroup",
            name="kind",
            field=models.CharField(
                choices=[("course", "正课"), ("self_study", "自习")],
                max_length=20,
                unique=True,
            ),
        ),
        migrations.RunPython(
            seed_export_parameters, migrations.RunPython.noop
        ),
        migrations.RemoveField(
            model_name="timeslot",
            name="weight",
        ),
        migrations.RemoveField(
            model_name="coursesession",
            name="weight",
        ),
    ]
