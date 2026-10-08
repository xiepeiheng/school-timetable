from datetime import date

from django.test import TestCase

from timetable import services
from timetable.exporting import build_monthly_workbook, build_teacher_workbook
from timetable.models import (
    CourseSession,
    ReportGroup,
    ScheduleTemplate,
    SchoolClass,
    Subject,
    Teacher,
    TeachingAssignment,
    TemplateEntry,
    TimeSlot,
)


class ServiceTestBase(TestCase):
    def setUp(self):
        self.chinese = Subject.objects.create(name="语文", sort_order=1)
        self.math = Subject.objects.create(name="数学", sort_order=2)
        self.t_ma = Teacher.objects.create(name="马老师", subject=self.chinese)
        self.t_wang = Teacher.objects.create(name="王老师", subject=self.math)
        self.c1 = SchoolClass.objects.create(name="2601", sort_order=1)
        self.c2 = SchoolClass.objects.create(name="2602", sort_order=2)
        self.slot_early = TimeSlot.objects.create(
            name="早读", sort_order=0, weight="1.00"
        )
        self.slot_1 = TimeSlot.objects.create(name="一", sort_order=1, weight="1.00")
        self.slot_4 = TimeSlot.objects.create(name="四", sort_order=4, weight="2.00")
        TeachingAssignment.objects.create(
            school_class=self.c1, subject=self.chinese, teacher=self.t_ma
        )
        TeachingAssignment.objects.create(
            school_class=self.c1, subject=self.math, teacher=self.t_wang
        )
        # 模板：周一 2601 早读语文、一数学；周二 2601 早读语文
        self.tpl = ScheduleTemplate.objects.create(name="基准模板")
        TemplateEntry.objects.create(
            template=self.tpl,
            school_class=self.c1,
            weekday=1,
            time_slot=self.slot_early,
            subject=self.chinese,
        )
        TemplateEntry.objects.create(
            template=self.tpl,
            school_class=self.c1,
            weekday=1,
            time_slot=self.slot_1,
            subject=self.math,
        )
        TemplateEntry.objects.create(
            template=self.tpl,
            school_class=self.c1,
            weekday=2,
            time_slot=self.slot_early,
            subject=self.chinese,
        )


class GenerateSessionsTest(ServiceTestBase):
    def test_generate_week_with_assignments(self):
        # 2026-09-07 是周一
        start, end = date(2026, 9, 7), date(2026, 9, 13)
        result = services.generate_sessions(self.tpl, start, end)
        self.assertEqual(result["created"], 3)
        s = CourseSession.objects.get(date=date(2026, 9, 7), time_slot=self.slot_1)
        self.assertEqual(s.teacher, self.t_wang)
        self.assertEqual(s.source, CourseSession.Source.TEMPLATE)
        self.assertEqual(s.flag, CourseSession.Flag.NORMAL)

    def test_fill_blank_keeps_existing(self):
        CourseSession.objects.create(
            date=date(2026, 9, 7),
            time_slot=self.slot_1,
            school_class=self.c1,
            subject=self.chinese,
            teacher=self.t_ma,
        )
        result = services.generate_sessions(
            self.tpl, date(2026, 9, 7), date(2026, 9, 13), overwrite=False
        )
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["skipped"], 1)
        s = CourseSession.objects.get(date=date(2026, 9, 7), time_slot=self.slot_1)
        self.assertEqual(s.subject, self.chinese)


class BatchOpsTest(ServiceTestBase):
    def setUp(self):
        super().setUp()
        services.generate_sessions(self.tpl, date(2026, 9, 7), date(2026, 9, 13))

    def test_copy_day(self):
        result = services.copy_day(date(2026, 9, 7), date(2026, 9, 9))
        self.assertEqual(result["copied"], 2)
        self.assertEqual(
            CourseSession.objects.filter(date=date(2026, 9, 9)).count(), 2
        )

    def test_clear_range(self):
        result = services.clear_range(
            date(2026, 9, 7), date(2026, 9, 7), time_slot_ids=[self.slot_1.id]
        )
        self.assertEqual(result["deleted"], 1)
        self.assertFalse(
            CourseSession.objects.filter(
                date=date(2026, 9, 7), time_slot=self.slot_1
            ).exists()
        )

    def test_bulk_upsert_and_clear_cell(self):
        services.bulk_upsert_sessions(
            [
                {
                    "date": date(2026, 9, 10),
                    "time_slot": self.slot_4.id,
                    "school_class": self.c1.id,
                    "subject": self.chinese.id,
                    "teacher": self.t_ma.id,
                }
            ]
        )
        s = CourseSession.objects.get(date=date(2026, 9, 10), time_slot=self.slot_4)
        self.assertEqual(s.teacher, self.t_ma)
        self.assertEqual(s.weight, 2)  # 快照 slot_4 的权重
        services.bulk_upsert_sessions(
            [
                {
                    "date": date(2026, 9, 10),
                    "time_slot": self.slot_4.id,
                    "school_class": self.c1.id,
                    "subject": None,
                }
            ]
        )
        self.assertFalse(
            CourseSession.objects.filter(
                date=date(2026, 9, 10), time_slot=self.slot_4
            ).exists()
        )

    def test_bulk_sets_flag(self):
        services.bulk_upsert_sessions(
            [
                {
                    "date": date(2026, 9, 11),
                    "time_slot": self.slot_1.id,
                    "school_class": self.c1.id,
                    "subject": self.chinese.id,
                    "teacher": self.t_ma.id,
                    "flag": CourseSession.Flag.ABNORMAL,
                    "note": "考试",
                }
            ]
        )
        s = CourseSession.objects.get(date=date(2026, 9, 11), time_slot=self.slot_1)
        self.assertEqual(s.flag, CourseSession.Flag.ABNORMAL)
        self.assertEqual(s.note, "考试")


class SwapSessionsTest(ServiceTestBase):
    def test_swap_only_subject_and_teacher(self):
        a = CourseSession.objects.create(
            date=date(2026, 9, 7),
            time_slot=self.slot_early,
            school_class=self.c1,
            subject=self.chinese,
            teacher=self.t_ma,
            weight="1.00",
        )
        b = CourseSession.objects.create(
            date=date(2026, 9, 8),
            time_slot=self.slot_4,
            school_class=self.c2,
            subject=self.math,
            teacher=self.t_wang,
            weight="2.00",
        )
        services.swap_sessions(a.id, b.id)
        a.refresh_from_db()
        b.refresh_from_db()
        # 学科+教师互换
        self.assertEqual(a.subject, self.math)
        self.assertEqual(a.teacher, self.t_wang)
        self.assertEqual(b.subject, self.chinese)
        self.assertEqual(b.teacher, self.t_ma)
        # 位置/权重不动
        self.assertEqual(a.date, date(2026, 9, 7))
        self.assertEqual(a.time_slot, self.slot_early)
        self.assertEqual(str(a.weight), "1.00")
        self.assertEqual(b.date, date(2026, 9, 8))
        self.assertEqual(b.time_slot, self.slot_4)
        self.assertEqual(str(b.weight), "2.00")
        # 两格都被标记为换课并写了备注
        self.assertEqual(a.flag, CourseSession.Flag.SWAP)
        self.assertEqual(b.flag, CourseSession.Flag.SWAP)
        self.assertTrue(a.note.startswith("调课："))
        self.assertTrue(b.note.startswith("调课："))

    def test_swap_with_self_rejected(self):
        from common.exceptions import BusinessException

        a = CourseSession.objects.create(
            date=date(2026, 9, 7),
            time_slot=self.slot_early,
            school_class=self.c1,
            subject=self.chinese,
            teacher=self.t_ma,
        )
        with self.assertRaises(BusinessException):
            services.swap_sessions(a.id, a.id)


class TemplateFromWeekTest(ServiceTestBase):
    def test_requires_full_monday_sunday(self):
        from common.exceptions import BusinessException

        with self.assertRaises(BusinessException):
            services.create_template_from_week(
                "x", date(2026, 9, 7), date(2026, 9, 10)
            )

    def test_create_from_week(self):
        services.generate_sessions(self.tpl, date(2026, 9, 7), date(2026, 9, 13))
        new_tpl = services.create_template_from_week(
            "拷贝模板", date(2026, 9, 7), date(2026, 9, 13)
        )
        self.assertEqual(new_tpl.entries.count(), 3)


class TemplateOpsTest(ServiceTestBase):
    def test_purge_entries_on_slot_deactivate(self):
        self.assertTrue(
            self.tpl.entries.filter(time_slot=self.slot_early).exists()
        )
        deleted = services.purge_template_entries_for_slot(self.slot_early.id)
        self.assertGreater(deleted, 0)
        self.assertFalse(
            self.tpl.entries.filter(time_slot=self.slot_early).exists()
        )

    def test_generate_skips_inactive_slots(self):
        self.slot_1.is_active = False
        self.slot_1.save()
        services.generate_sessions(self.tpl, date(2026, 9, 7), date(2026, 9, 13))
        self.assertFalse(
            CourseSession.objects.filter(
                date=date(2026, 9, 7), time_slot=self.slot_1
            ).exists()
        )

    def test_bulk_entries_and_duplicate(self):
        services.bulk_upsert_template_entries(
            [
                {
                    "template": self.tpl.id,
                    "school_class": self.c2.id,
                    "weekday": 3,
                    "time_slot": self.slot_1.id,
                    "subject": self.math.id,
                }
            ]
        )
        self.assertTrue(
            self.tpl.entries.filter(
                school_class=self.c2, weekday=3, time_slot=self.slot_1
            ).exists()
        )
        before = self.tpl.entries.count()
        new = services.duplicate_template(self.tpl, "副本")
        self.assertEqual(new.entries.count(), before)


class ExportTest(TestCase):
    def setUp(self):
        self.chinese = Subject.objects.create(name="语文", sort_order=1)
        self.t_ma = Teacher.objects.create(name="马老师", subject=self.chinese)
        self.c1 = SchoolClass.objects.create(name="2601", sort_order=1)
        groups = {}
        for kind, order in [
            ("early_read", 0),
            ("morning", 1),
            ("afternoon", 2),
            ("self_study", 3),
        ]:
            groups[kind], _ = ReportGroup.objects.get_or_create(
                kind=kind, defaults={"sort_order": order}
            )
        self.slot_early = TimeSlot.objects.create(
            name="早读", sort_order=0, report_group=groups["early_read"]
        )
        self.slot_1 = TimeSlot.objects.create(
            name="一", sort_order=1, report_group=groups["morning"]
        )
        TeachingAssignment.objects.create(
            school_class=self.c1, subject=self.chinese, teacher=self.t_ma
        )
        CourseSession.objects.create(
            date=date(2026, 9, 7),
            time_slot=self.slot_1,
            school_class=self.c1,
            subject=self.chinese,
            teacher=self.t_ma,
        )
        CourseSession.objects.create(
            date=date(2026, 9, 7),
            time_slot=self.slot_early,
            school_class=self.c1,
            subject=self.chinese,
            teacher=self.t_ma,
        )
        self.tpl = ScheduleTemplate.objects.create(name="模板")
        TemplateEntry.objects.create(
            template=self.tpl,
            school_class=self.c1,
            weekday=1,
            time_slot=self.slot_1,
            subject=self.chinese,
        )

    def test_build_workbook(self):
        wb = build_monthly_workbook(2026, 9, self.tpl)
        self.assertEqual(
            wb.sheetnames,
            [
                "详细课表",
                "周一至周五课",
                "周一至周五自习",
                "周六日课",
                "周六日自习",
                "监考",
            ],
        )
        # 周一至周五课：第一行数据是马老师，周一 9.7 上午 = 1
        ws = wb["周一至周五课"]
        self.assertEqual(ws.cell(row=3, column=3).value, "马老师")
        self.assertEqual(ws.cell(row=3, column=5).value, 1)
        # 周一至周五自习：早读 = 1
        ws2 = wb["周一至周五自习"]
        self.assertEqual(ws2.cell(row=3, column=5).value, 1)
        # 监考只有 4 列
        self.assertEqual(wb["监考"].max_column, 4)

    def test_teacher_workbook(self):
        wb = build_teacher_workbook(date(2026, 9, 7), date(2026, 9, 8))
        self.assertIn("语文-马老师", wb.sheetnames)
        ws = wb["语文-马老师"]
        headers = [
            ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)
        ]
        self.assertEqual(headers[0], "日期")
        self.assertEqual(headers[1], "星期")
        self.assertEqual(headers[-1], "合计")
        col_one = headers.index("一") + 1
        # 9.7 第一节是 2601
        self.assertEqual(ws.cell(row=2, column=col_one).value, "2601")
        # 9.8（第二天）没有课，格子为空
        self.assertIsNone(ws.cell(row=3, column=col_one).value)
