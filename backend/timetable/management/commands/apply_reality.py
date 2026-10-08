"""按《实际情况.md》把 2026-09-06 ~ 2026-10-11 的实际课程排入系统。

可重复执行：先清空区间内的课程记录，再按模板生成基准（工作日），
然后逐日套用以下调整（模板统一使用「9月定」）：

- 09-06 周日  只上周四的 晚一/晚二/晚三
- 09-12 周六  上周一（全天，含早读/晚自习）
- 09-13 周日  上周二（全天）
- 09-16 周三  早读正常；一~四 换成周五的一~四；五~八、晚自习正常周三
- 09-17 周四  白天正常；晚一/晚二/晚三 = 置空
- 09-18 周五  只留早读；一~八 + 晚自习 = 置空
- 09-19 周六  全天放假
- 09-20 周日  只上周五的 晚一/晚二/晚三
- 09-24 周四  一~七正常；八 + 晚自习 = 停
- 09-25 周五  全天放假（中秋）
- 09-26 周六  只上周四的 晚一/晚二/晚三
- 09-27 周日  上周五（全天）
- 09-30 周三  课7之后放假（八 + 晚自习停）
- 10-01 ~ 10-06  国庆放假，全空
- 10-07 周三  只上周三的 晚一/晚二/晚三
- 10-10、10-11  周末空

基础资料（学科/教师/班级/任课关系/班主任）不受影响。

用法：
    python manage.py apply_reality
    python manage.py apply_reality --template "9月标准模板"
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from timetable import services
from timetable.models import (
    CourseSession,
    ScheduleTemplate,
    SchoolClass,
    Subject,
    TeachingAssignment,
    TimeSlot,
)

START = date(2026, 9, 6)
END = date(2026, 10, 11)

# 一~八 的时段名
PERIODS = ["一", "二", "三", "四", "五", "六", "七", "八"]
EVENING = ["晚一", "晚二", "晚三"]


class Command(BaseCommand):
    help = "按实际情况把 2026-09-06 ~ 2026-10-11 的实际课程排入系统"

    def add_arguments(self, parser):
        parser.add_argument(
            "--template", default="", help="模板名称；默认取默认模板"
        )

    @transaction.atomic
    def handle(self, *args, **options):
        template = self._get_template(options["template"])
        self.stdout.write(f"使用模板：{template.name}")

        # 清空区间（不保留任何旧课程记录），再按模板生成工作日的基准
        CourseSession.objects.filter(date__range=(START, END)).delete()
        services.generate_sessions(template, START, END, overwrite=True)
        self.stdout.write("已生成基准（工作日）")

        self._apply_specials()
        self._apply_legacy_patches()

        total = CourseSession.objects.filter(date__range=(START, END)).count()
        self.stdout.write(
            self.style.SUCCESS(f"完成：{START} ~ {END}，共 {total} 条课程记录")
        )

    # ── 辅助 ──

    def _get_template(self, name: str) -> ScheduleTemplate:
        qs = ScheduleTemplate.objects.all()
        if name:
            template = qs.filter(name=name).first()
            if not template:
                raise CommandError(f"找不到模板：{name}")
            return template
        template = qs.filter(is_default=True).first() or qs.first()
        if not template:
            raise CommandError("没有可用模板，请先导入/新建模板")
        return template

    def _slot_ids(self, names: list[str] | None) -> set[int] | None:
        if not names:
            return None
        return set(TimeSlot.objects.filter(name__in=names).values_list("id", flat=True))

    def _clear_day(self, day: date) -> None:
        CourseSession.objects.filter(date=day).delete()

    def _delete_slots(self, day: date, names: list[str]) -> None:
        CourseSession.objects.filter(date=day, time_slot__name__in=names).delete()

    def _copy_day(
        self, src: date, dst: date, slot_names: list[str] | None = None
    ) -> int:
        """把 src 的课程（可选指定时段）复制到 dst，先清空 dst 对应范围。"""
        scope = self._slot_ids(slot_names)
        target = CourseSession.objects.filter(date=dst)
        source = CourseSession.objects.filter(date=src).select_related("time_slot")
        if scope:
            target = target.filter(time_slot_id__in=scope)
            source = source.filter(time_slot_id__in=scope)
        target.delete()
        objs = [
            CourseSession(
                date=dst,
                time_slot=s.time_slot,
                school_class=s.school_class,
                subject=s.subject,
                teacher=s.teacher,
                weight=s.weight,
                flag=s.flag,
                source=CourseSession.Source.MANUAL,
                note=s.note,
            )
            for s in source
        ]
        CourseSession.objects.bulk_create(objs)
        return len(objs)

    def _patch_cell(
        self, day: date, class_name: str, slot_name: str, subject_name: str
    ) -> None:
        """把某天某班某时段的学科改成 subject_name，教师取任课关系。"""
        subject = Subject.objects.filter(name=subject_name).first()
        klass = SchoolClass.objects.filter(name=class_name).first()
        if not subject or not klass:
            raise CommandError(f"修正目标无效：{class_name} / {subject_name}")
        teacher_id = (
            TeachingAssignment.objects.filter(school_class=klass, subject=subject)
            .values_list("teacher_id", flat=True)
            .first()
        )
        updated = CourseSession.objects.filter(
            date=day, school_class=klass, time_slot__name=slot_name
        ).update(
            subject=subject,
            teacher_id=teacher_id,
            source=CourseSession.Source.MANUAL,
        )
        if not updated:
            raise CommandError(f"修正目标不存在：{day} {class_name} {slot_name}")

    # ── 逐日调整 ──

    def _apply_specials(self) -> None:
        D = date

        # 第 0 周：09-07 周一 ~ 09-11 周五 为标准周，作为抄录来源
        monday, tuesday, wednesday, thursday, friday = (
            D(2026, 9, 7),
            D(2026, 9, 8),
            D(2026, 9, 9),
            D(2026, 9, 10),
            D(2026, 9, 11),
        )

        # 09-06 周日：只上周四晚自习
        self._copy_day(thursday, D(2026, 9, 6), EVENING)

        # 09-12 周六 上周一；09-13 周日 上周二（全天）
        self._copy_day(monday, D(2026, 9, 12))
        self._copy_day(tuesday, D(2026, 9, 13))

        # 09-15 周二：照常（不换课）
        # 09-16 周三：一~四 换成周五的一~四
        self._copy_day(friday, D(2026, 9, 16), ["一", "二", "三", "四"])

        # 09-17 周四：三节晚自习置空（白天正常）
        self._delete_slots(D(2026, 9, 17), EVENING)

        # 09-18 周五：只留早读（一~八 + 晚自习置空）
        self._delete_slots(
            D(2026, 9, 18),
            ["一", "二", "三", "四", "五", "六", "七", "八", *EVENING],
        )

        # 09-19 周六：全天放假
        self._clear_day(D(2026, 9, 19))

        # 09-20 周日：只上周五晚自习
        self._copy_day(friday, D(2026, 9, 20), EVENING)

        # 09-24 周四：课七之后放假（八 + 晚自习停）
        self._delete_slots(D(2026, 9, 24), ["八", *EVENING])

        # 09-25 周五：全天放假（中秋）
        self._clear_day(D(2026, 9, 25))

        # 09-26 周六：只上周四晚自习
        self._copy_day(thursday, D(2026, 9, 26), EVENING)

        # 09-27 周日：上周五（全天）
        self._copy_day(friday, D(2026, 9, 27))

        # 09-30 周三：课7之后放假（八 + 晚自习停）
        self._delete_slots(D(2026, 9, 30), ["八", *EVENING])

        # 国庆 10-01 ~ 10-06：全空
        day = D(2026, 10, 1)
        while day <= D(2026, 10, 6):
            self._clear_day(day)
            day += timedelta(days=1)

        # 10-07 周三：只上周三晚自习
        self._clear_day(D(2026, 10, 7))
        self._copy_day(wednesday, D(2026, 10, 7), EVENING)

        # 10-10、10-11：周末空
        self._clear_day(D(2026, 10, 10))
        self._clear_day(D(2026, 10, 11))

    def _apply_legacy_patches(self) -> None:
        """09-06 用「9月」、09-07 用「9月改」；与 9月定 的差异只此 8 格，一次性修正。"""
        D = date
        # 09-06（9月）周四晚自习
        self._patch_cell(D(2026, 9, 6), "2601", "晚二", "物理")
        self._patch_cell(D(2026, 9, 6), "2602", "晚三", "英语")
        self._patch_cell(D(2026, 9, 6), "2604", "晚一", "语文")
        self._patch_cell(D(2026, 9, 6), "2604", "晚二", "历史")
        self._patch_cell(D(2026, 9, 6), "2606", "晚二", "语文")
        self._patch_cell(D(2026, 9, 6), "2609", "晚三", "生物")
        # 09-07（9月改）周一
        self._patch_cell(D(2026, 9, 7), "2607", "晚一", "地理")
        self._patch_cell(D(2026, 9, 7), "2609", "早读", "历史")

