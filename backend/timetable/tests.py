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


class ApplyTemplateCellTest(ServiceTestBase):
    def setUp(self):
        super().setUp()
        self.target = date(2026, 10, 10)

    def test_fills_current_class_and_snapshots_weight(self):
        self.slot_early.weight = "0.50"
        self.slot_early.save(update_fields=["weight"])

        result = services.apply_template_cell(
            template_id=self.tpl.id,
            target=self.target,
            time_slot_id=self.slot_early.id,
            source_weekday=1,
            school_class_ids=[self.c1.id],
            overwrite=False,
        )

        self.assertEqual(
            result, {"created": 1, "updated": 0, "skipped": 0, "matched": 1}
        )
        s = CourseSession.objects.get(
            date=self.target, time_slot=self.slot_early, school_class=self.c1
        )
        self.assertEqual(s.subject, self.chinese)
        self.assertEqual(s.teacher, self.t_ma)
        self.assertEqual(str(s.weight), "0.50")
        self.assertEqual(s.source, CourseSession.Source.MANUAL)
        self.assertEqual(s.flag, CourseSession.Flag.NORMAL)
        self.assertEqual(s.note, "")

    def test_all_classes_skips_classes_without_template_entry(self):
        result = services.apply_template_cell(
            template_id=self.tpl.id,
            target=self.target,
            time_slot_id=self.slot_early.id,
            source_weekday=1,
            school_class_ids=None,
            overwrite=False,
        )

        self.assertEqual(result["matched"], 1)
        self.assertTrue(
            CourseSession.objects.filter(
                date=self.target, time_slot=self.slot_early, school_class=self.c1
            ).exists()
        )
        self.assertFalse(
            CourseSession.objects.filter(
                date=self.target, time_slot=self.slot_early, school_class=self.c2
            ).exists()
        )

    def test_only_fill_blank_keeps_existing(self):
        CourseSession.objects.create(
            date=self.target,
            time_slot=self.slot_early,
            school_class=self.c1,
            subject=self.math,
            teacher=self.t_wang,
            weight="2.00",
            flag=CourseSession.Flag.ABNORMAL,
            note="旧备注",
        )

        result = services.apply_template_cell(
            template_id=self.tpl.id,
            target=self.target,
            time_slot_id=self.slot_early.id,
            source_weekday=1,
            school_class_ids=[self.c1.id],
            overwrite=False,
        )

        self.assertEqual(result["created"], 0)
        self.assertEqual(result["skipped"], 1)
        s = CourseSession.objects.get(
            date=self.target, time_slot=self.slot_early, school_class=self.c1
        )
        self.assertEqual(s.subject, self.math)
        self.assertEqual(s.teacher, self.t_wang)
        self.assertEqual(s.flag, CourseSession.Flag.ABNORMAL)
        self.assertEqual(s.note, "旧备注")

    def test_overwrite_replaces_existing_and_resets_flag_note(self):
        CourseSession.objects.create(
            date=self.target,
            time_slot=self.slot_early,
            school_class=self.c1,
            subject=self.math,
            teacher=self.t_wang,
            weight="2.00",
            flag=CourseSession.Flag.ABNORMAL,
            note="旧备注",
        )

        result = services.apply_template_cell(
            template_id=self.tpl.id,
            target=self.target,
            time_slot_id=self.slot_early.id,
            source_weekday=1,
            school_class_ids=[self.c1.id],
            overwrite=True,
        )

        self.assertEqual(result["created"], 0)
        self.assertEqual(result["updated"], 1)
        s = CourseSession.objects.get(
            date=self.target, time_slot=self.slot_early, school_class=self.c1
        )
        self.assertEqual(s.subject, self.chinese)
        self.assertEqual(s.teacher, self.t_ma)
        self.assertEqual(str(s.weight), "1.00")
        self.assertEqual(s.flag, CourseSession.Flag.NORMAL)
        self.assertEqual(s.note, "")

    def test_empty_template_cell_returns_zero(self):
        result = services.apply_template_cell(
            template_id=self.tpl.id,
            target=self.target,
            time_slot_id=self.slot_early.id,
            source_weekday=3,
            school_class_ids=None,
            overwrite=True,
        )

        self.assertEqual(
            result, {"created": 0, "updated": 0, "skipped": 0, "matched": 0}
        )
        self.assertFalse(CourseSession.objects.filter(date=self.target).exists())


class ApplySubjectCellTest(ServiceTestBase):
    def setUp(self):
        super().setUp()
        self.target = date(2026, 10, 10)
        self.c3 = SchoolClass.objects.create(
            name="2603", sort_order=3, is_active=False
        )

    def test_fills_active_classes_and_counts_missing_teacher(self):
        self.slot_early.weight = "0.50"
        self.slot_early.save(update_fields=["weight"])

        result = services.apply_subject_cell(
            target=self.target,
            time_slot_id=self.slot_early.id,
            subject_id=self.math.id,
            school_class_ids=None,
            overwrite=False,
        )

        self.assertEqual(
            result,
            {
                "created": 2,
                "updated": 0,
                "skipped": 0,
                "matched": 2,
                "missing_teacher": 1,
            },
        )
        s1 = CourseSession.objects.get(
            date=self.target, time_slot=self.slot_early, school_class=self.c1
        )
        self.assertEqual(s1.subject, self.math)
        self.assertEqual(s1.teacher, self.t_wang)
        self.assertEqual(str(s1.weight), "0.50")
        self.assertEqual(s1.source, CourseSession.Source.MANUAL)
        self.assertEqual(s1.flag, CourseSession.Flag.NORMAL)
        self.assertEqual(s1.note, "")
        s2 = CourseSession.objects.get(
            date=self.target, time_slot=self.slot_early, school_class=self.c2
        )
        self.assertIsNone(s2.teacher)
        self.assertFalse(
            CourseSession.objects.filter(
                date=self.target, time_slot=self.slot_early, school_class=self.c3
            ).exists()
        )

    def test_only_fill_blank_then_overwrite(self):
        CourseSession.objects.create(
            date=self.target,
            time_slot=self.slot_early,
            school_class=self.c1,
            subject=self.chinese,
            teacher=self.t_ma,
        )
        result = services.apply_subject_cell(
            target=self.target,
            time_slot_id=self.slot_early.id,
            subject_id=self.math.id,
            school_class_ids=[self.c1.id],
            overwrite=False,
        )
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["matched"], 1)
        s = CourseSession.objects.get(
            date=self.target, time_slot=self.slot_early, school_class=self.c1
        )
        self.assertEqual(s.subject, self.chinese)

        result = services.apply_subject_cell(
            target=self.target,
            time_slot_id=self.slot_early.id,
            subject_id=self.math.id,
            school_class_ids=[self.c1.id],
            overwrite=True,
        )
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["missing_teacher"], 0)
        s.refresh_from_db()
        self.assertEqual(s.subject, self.math)
        self.assertEqual(s.teacher, self.t_wang)

    def test_custom_scope_only_touches_selected_class(self):
        result = services.apply_subject_cell(
            target=self.target,
            time_slot_id=self.slot_early.id,
            subject_id=self.chinese.id,
            school_class_ids=[self.c2.id],
            overwrite=False,
        )
        self.assertEqual(result["matched"], 1)
        self.assertTrue(
            CourseSession.objects.filter(
                date=self.target, time_slot=self.slot_early, school_class=self.c2
            ).exists()
        )
        self.assertFalse(
            CourseSession.objects.filter(
                date=self.target, time_slot=self.slot_early, school_class=self.c1
            ).exists()
        )


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
            name="早读",
            sort_order=0,
            weight="0.50",
            report_group=groups["early_read"],
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
            weight=self.slot_1.weight,
        )
        CourseSession.objects.create(
            date=date(2026, 9, 7),
            time_slot=self.slot_early,
            school_class=self.c1,
            subject=self.chinese,
            teacher=self.t_ma,
            weight=self.slot_early.weight,
        )

    def test_build_workbook(self):
        wb = build_monthly_workbook(date(2026, 9, 7), date(2026, 9, 8))
        self.assertEqual(
            wb.sheetnames,
            [
                "周一至周五课",
                "周一至周五自习",
                "周六日课",
                "周六日自习",
                "课时汇总",
            ],
        )
        # 周一至周五课：第一行数据是马老师，周一 9.7 上午 = 1
        ws = wb["周一至周五课"]
        self.assertEqual(ws.cell(row=3, column=3).value, "马老师")
        self.assertEqual(ws.cell(row=3, column=5).value, 1)
        # 周一至周五自习：早读 = 1
        ws2 = wb["周一至周五自习"]
        self.assertEqual(ws2.cell(row=3, column=5).value, 1)

        # 课时汇总：课 1 节、自习 1 节；早读系数 0.5
        summary = wb["课时汇总"]
        self.assertEqual(summary.cell(row=2, column=3).value, "马老师")
        self.assertEqual(summary.cell(row=2, column=5).value, 1)
        self.assertEqual(summary.cell(row=2, column=6).value, 1)
        self.assertEqual(summary.cell(row=2, column=7).value, 2)
        self.assertEqual(summary.cell(row=2, column=8).value, 1.0)
        self.assertEqual(summary.cell(row=2, column=9).value, 0.5)
        self.assertEqual(summary.cell(row=2, column=10).value, 1.5)

    def test_teacher_workbook(self):
        wb = build_teacher_workbook(date(2026, 9, 7), date(2026, 9, 8))
        self.assertIn("语文-马老师", wb.sheetnames)
        ws = wb["语文-马老师"]
        headers = [
            ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)
        ]
        self.assertEqual(headers[0], "日期")
        self.assertEqual(headers[1], "星期")
        self.assertEqual(headers[-2], "合计")
        self.assertEqual(headers[-1], "按系数合计")
        col_early = headers.index("早读") + 1
        col_one = headers.index("一") + 1
        total_col = headers.index("合计") + 1
        weight_col = headers.index("按系数合计") + 1
        # 9.7 第一节是 2601
        self.assertEqual(ws.cell(row=2, column=col_one).value, "2601")
        # 9.8（第二天）没有课，格子为空
        self.assertIsNone(ws.cell(row=3, column=col_one).value)

        # 表尾两行：节数合计 / 按系数合计
        self.assertEqual(ws.cell(row=4, column=1).value, "合计")
        self.assertEqual(ws.cell(row=4, column=col_early).value, 1)
        self.assertEqual(ws.cell(row=4, column=col_one).value, 1)
        self.assertEqual(ws.cell(row=4, column=total_col).value, 2)
        self.assertEqual(ws.cell(row=5, column=1).value, "按系数合计")
        self.assertEqual(ws.cell(row=5, column=col_early).value, 0.5)
        self.assertEqual(ws.cell(row=5, column=col_one).value, 1.0)
        self.assertEqual(ws.cell(row=5, column=weight_col).value, 1.5)

        # 按节次统计：2601 早读 1、一 1、合计 2
        self.assertEqual(ws.cell(row=7, column=1).value, "任课统计（按节次）")
        self.assertEqual(
            [ws.cell(row=8, column=c).value for c in range(1, 5)],
            ["班级", "早读", "一", "合计"],
        )
        self.assertEqual(
            [ws.cell(row=9, column=c).value for c in range(1, 5)],
            ["2601", 1, 1, 2],
        )
        self.assertEqual(
            [ws.cell(row=10, column=c).value for c in range(1, 5)],
            ["合计", 1, 1, 2],
        )

        # 按学科统计：2601 语文 2
        self.assertEqual(ws.cell(row=12, column=1).value, "任课统计（按学科）")
        self.assertEqual(
            [ws.cell(row=13, column=c).value for c in range(1, 4)],
            ["班级", "语文", "合计"],
        )
        self.assertEqual(
            [ws.cell(row=14, column=c).value for c in range(1, 4)],
            ["2601", 2, 2],
        )
        self.assertEqual(
            [ws.cell(row=15, column=c).value for c in range(1, 4)],
            ["合计", 2, 2],
        )

        # 标注说明区在统计表之后
        self.assertEqual(ws.cell(row=17, column=1).value, "标注说明")

    def test_teacher_subject_table_supports_substitution(self):
        math = Subject.objects.create(name="数学", sort_order=2)
        c2 = SchoolClass.objects.create(name="2602", sort_order=2)
        CourseSession.objects.create(
            date=date(2026, 9, 8),
            time_slot=self.slot_1,
            school_class=c2,
            subject=math,
            teacher=self.t_ma,
            weight=self.slot_1.weight,
        )

        wb = build_teacher_workbook(date(2026, 9, 7), date(2026, 9, 8))
        ws = wb["语文-马老师"]
        title_row = next(
            r
            for r in range(1, ws.max_row + 1)
            if ws.cell(row=r, column=1).value == "任课统计（按学科）"
        )
        self.assertEqual(
            [ws.cell(row=title_row + 1, column=c).value for c in range(1, 5)],
            ["班级", "语文", "数学", "合计"],
        )
        self.assertEqual(
            [ws.cell(row=title_row + 2, column=c).value for c in range(1, 5)],
            ["2601", 2, 0, 2],
        )
        self.assertEqual(
            [ws.cell(row=title_row + 3, column=c).value for c in range(1, 5)],
            ["2602", 0, 1, 1],
        )
        self.assertEqual(
            [ws.cell(row=title_row + 4, column=c).value for c in range(1, 5)],
            ["合计", 2, 1, 3],
        )
