from datetime import date

from django.test import TestCase

from timetable import services
from timetable.exporting import build_teacher_workbook
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
        self.slot_early = TimeSlot.objects.create(name="早读", sort_order=0)
        self.slot_1 = TimeSlot.objects.create(name="一", sort_order=1)
        self.slot_4 = TimeSlot.objects.create(name="四", sort_order=4)
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

    def test_fills_current_class(self):
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
        )
        b = CourseSession.objects.create(
            date=date(2026, 9, 8),
            time_slot=self.slot_4,
            school_class=self.c2,
            subject=self.math,
            teacher=self.t_wang,
        )
        services.swap_sessions(a.id, b.id)
        a.refresh_from_db()
        b.refresh_from_db()
        # 学科+教师互换
        self.assertEqual(a.subject, self.math)
        self.assertEqual(a.teacher, self.t_wang)
        self.assertEqual(b.subject, self.chinese)
        self.assertEqual(b.teacher, self.t_ma)
        # 位置不动
        self.assertEqual(a.date, date(2026, 9, 7))
        self.assertEqual(a.time_slot, self.slot_early)
        self.assertEqual(b.date, date(2026, 9, 8))
        self.assertEqual(b.time_slot, self.slot_4)
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
        self.chinese = Subject.objects.create(
            name="语文", sort_order=1, is_main=True
        )
        self.math = Subject.objects.create(name="数学", sort_order=2, is_main=True)
        self.t_ma = Teacher.objects.create(name="马老师", subject=self.chinese)
        self.t_wang = Teacher.objects.create(name="王老师", subject=self.math)
        self.c1 = SchoolClass.objects.create(
            name="2601", sort_order=1, is_key_class=True
        )
        self.c2 = SchoolClass.objects.create(
            name="2602", sort_order=2, is_key_class=True
        )
        self.c3 = SchoolClass.objects.create(name="2603", sort_order=3)
        self.course_group, _ = ReportGroup.objects.get_or_create(
            kind="course", defaults={"sort_order": 0}
        )
        self.study_group, _ = ReportGroup.objects.get_or_create(
            kind="self_study", defaults={"sort_order": 1}
        )
        self.slot_early = TimeSlot.objects.create(
            name="早读", sort_order=0, report_group=self.study_group
        )
        self.slot_1 = TimeSlot.objects.create(
            name="一", sort_order=1, report_group=self.course_group
        )
        self.s1 = CourseSession.objects.create(
            date=date(2026, 9, 7),
            time_slot=self.slot_1,
            school_class=self.c1,
            subject=self.chinese,
            teacher=self.t_ma,
        )
        self.s2 = CourseSession.objects.create(
            date=date(2026, 9, 7),
            time_slot=self.slot_early,
            school_class=self.c1,
            subject=self.chinese,
            teacher=self.t_ma,
        )

    def find_row(self, ws, label):
        for r in range(1, ws.max_row + 1):
            if ws.cell(row=r, column=1).value == label:
                return r
        self.fail(f"找不到行：{label}")

    def test_teacher_workbook(self):
        wb = build_teacher_workbook(date(2026, 9, 7), date(2026, 9, 8))
        self.assertEqual(wb.sheetnames[0], "教师绩效汇总")
        self.assertIn("语文-马老师", wb.sheetnames)
        self.assertIn("班级-2601", wb.sheetnames)

        summary = wb["教师绩效汇总"]
        self.assertEqual(
            [summary.cell(row=1, column=c).value for c in range(1, 8)],
            [
                "教师姓名",
                "周一至周五课",
                "周一至周五自习",
                "周六日课",
                "周六日自习",
                "总课时",
                "最终绩效",
            ],
        )
        self.assertEqual(summary.cell(row=2, column=1).value, "马老师")
        self.assertEqual(summary.cell(row=2, column=2).value, 1)
        self.assertEqual(summary.cell(row=2, column=3).value, 1)
        self.assertEqual(summary.cell(row=2, column=4).value, 0)
        self.assertEqual(summary.cell(row=2, column=5).value, 0)
        self.assertEqual(summary.cell(row=2, column=6).value, 2)
        self.assertTrue(
            str(summary.cell(row=2, column=7).value).startswith(
                "='语文-马老师'!$B$"
            )
        )
        self.assertNotIn(
            "王老师",
            [
                summary.cell(row=r, column=1).value
                for r in range(2, summary.max_row + 1)
            ],
        )

        ws = wb["语文-马老师"]
        headers = []
        for c in range(1, ws.max_column + 1):
            value = ws.cell(row=1, column=c).value
            if value is None:
                break
            headers.append(value)
        self.assertEqual(headers[0], "日期")
        self.assertEqual(headers[1], "星期")
        self.assertEqual(headers[-1], "合计")
        self.assertNotIn("按系数合计", headers)
        col_early = headers.index("早读") + 1
        col_one = headers.index("一") + 1
        total_col = headers.index("合计") + 1
        self.assertEqual(ws.cell(row=2, column=col_one).value, "2601")
        self.assertIsNone(ws.cell(row=3, column=col_one).value)
        self.assertEqual(ws.cell(row=4, column=1).value, "合计")
        self.assertEqual(ws.cell(row=4, column=col_early).value, 1)
        self.assertEqual(ws.cell(row=4, column=col_one).value, 1)
        self.assertEqual(ws.cell(row=4, column=total_col).value, 2)

        # 按节次/按学科统计仍然保留
        self.find_row(ws, "任课统计（按节次）")
        self.find_row(ws, "任课统计（按学科）")

        # 绩效参数区
        param_title = self.find_row(ws, "绩效系数计算")
        self.assertEqual(ws.cell(row=param_title + 1, column=1).value, "教师系数")
        self.assertEqual(ws.cell(row=param_title + 1, column=2).value, 1.0)
        self.assertEqual(ws.cell(row=param_title + 2, column=1).value, "满课系数")
        self.assertEqual(ws.cell(row=param_title + 2, column=2).value, 12)
        self.assertEqual(ws.cell(row=param_title + 3, column=1).value, "超额倍数")
        self.assertEqual(ws.cell(row=param_title + 3, column=2).value, 1.5)

        # 按周工作量
        weekly_title = self.find_row(ws, "按周工作量（不满一周按一周）")
        self.assertEqual(ws.cell(row=weekly_title + 1, column=1).value, "周次")
        weekly_row = weekly_title + 2
        self.assertEqual(ws.cell(row=weekly_row, column=2).value, 1)
        self.assertEqual(ws.cell(row=weekly_row, column=3).value, 1)
        self.assertEqual(ws.cell(row=weekly_row, column=6).value, 2)
        self.assertTrue(
            str(ws.cell(row=weekly_row, column=7).value).startswith("=SUMIF(")
        )

        # 系数明细（按周）：2601 语文 正课 1 节，班级系数 1.1；自习 1 节，班级系数 1.0
        detail_title = self.find_row(ws, "系数明细（按周）")
        header_row = detail_title + 1
        self.assertEqual(ws.cell(row=header_row, column=1).value, "周次")
        self.assertEqual(ws.cell(row=header_row, column=4).value, "类别")
        self.assertEqual(ws.cell(row=header_row + 1, column=2).value, "2601")
        self.assertEqual(ws.cell(row=header_row + 1, column=4).value, "正课")
        self.assertEqual(ws.cell(row=header_row + 1, column=5).value, 1)
        self.assertEqual(ws.cell(row=header_row + 1, column=7).value, 1.1)
        self.assertEqual(ws.cell(row=header_row + 2, column=4).value, "自习")
        self.assertEqual(ws.cell(row=header_row + 2, column=5).value, 1)
        self.assertEqual(ws.cell(row=header_row + 2, column=7).value, 1.0)
        self.assertTrue(
            str(ws.cell(row=header_row + 1, column=8).value).startswith("=$B$")
        )

        self.assertEqual(
            ws.cell(row=self.find_row(ws, "原始正课节数"), column=2).value, 1
        )
        self.assertEqual(
            ws.cell(row=self.find_row(ws, "原始自习节数"), column=2).value, 1
        )
        self.assertEqual(
            ws.cell(row=self.find_row(ws, "原始总节数"), column=2).value, 2
        )
        self.assertTrue(
            str(
                ws.cell(
                    row=self.find_row(ws, "系数合计（未计超额）"), column=2
                ).value
            ).startswith("=SUM(J")
        )
        self.find_row(ws, "按周绩效合计")

        class_ws = wb["班级-2601"]
        self.assertEqual(
            [class_ws.cell(row=1, column=c).value for c in range(1, 5)],
            ["日期", "星期", "早读", "一"],
        )
        self.assertEqual(class_ws.cell(row=2, column=3).value, "语文 - 马老师")
        self.assertEqual(class_ws.cell(row=2, column=4).value, "语文 - 马老师")
        self.assertIsNone(class_ws.cell(row=3, column=3).value)

    def test_teacher_subject_table_supports_substitution(self):
        CourseSession.objects.create(
            date=date(2026, 9, 8),
            time_slot=self.slot_1,
            school_class=self.c2,
            subject=self.math,
            teacher=self.t_ma,
        )

        wb = build_teacher_workbook(date(2026, 9, 7), date(2026, 9, 8))
        ws = wb["语文-马老师"]
        detail_title = self.find_row(ws, "系数明细（按周）")
        header_row = detail_title + 1
        headers = [
            ws.cell(row=header_row, column=c).value for c in range(1, 11)
        ]
        self.assertEqual(
            headers,
            [
                "周次",
                "班级",
                "学科",
                "类别",
                "节数",
                "基准系数",
                "班级系数",
                "教师系数",
                "折算系数",
                "小计",
            ],
        )
        row_2602 = next(
            r
            for r in range(header_row + 1, ws.max_row + 1)
            if ws.cell(row=r, column=2).value == "2602"
        )
        self.assertEqual(ws.cell(row=row_2602, column=3).value, "数学")
        self.assertEqual(ws.cell(row=row_2602, column=4).value, "正课")
        self.assertEqual(ws.cell(row=row_2602, column=5).value, 1)
        self.assertTrue(
            str(ws.cell(row=row_2602, column=6).value).startswith("=IF($D")
        )
        self.assertEqual(ws.cell(row=row_2602, column=7).value, 1.1)

    def test_coefficients_prefilled_from_report_groups(self):
        self.course_group.coefficient = "1.20"
        self.course_group.save(update_fields=["coefficient"])
        self.study_group.coefficient = "0.60"
        self.study_group.save(update_fields=["coefficient"])

        wb = build_teacher_workbook(date(2026, 9, 7), date(2026, 9, 8))
        ws = wb["语文-马老师"]
        param_title = self.find_row(ws, "绩效系数计算")
        self.assertEqual(ws.cell(row=param_title + 4, column=2).value, 1.2)
        self.assertEqual(ws.cell(row=param_title + 5, column=2).value, 0.6)

    def test_cross_grade_and_non_main_subject(self):
        senior = Teacher.objects.create(
            name="陈海燕",
            subject=self.chinese,
            is_cross_grade=True,
            full_load_score=12,
        )
        music = Subject.objects.create(name="音乐", sort_order=3, is_main=False)
        CourseSession.objects.create(
            date=date(2026, 9, 8),
            time_slot=self.slot_1,
            school_class=self.c1,
            subject=self.chinese,
            teacher=senior,
        )
        CourseSession.objects.create(
            date=date(2026, 9, 7),
            time_slot=self.slot_1,
            school_class=self.c2,
            subject=music,
            teacher=senior,
        )

        wb = build_teacher_workbook(date(2026, 9, 7), date(2026, 9, 8))
        ws = wb["语文-陈海燕"]
        param_title = self.find_row(ws, "绩效系数计算")
        self.assertEqual(ws.cell(row=param_title + 1, column=2).value, 1.2)

        detail_title = self.find_row(ws, "系数明细（按周）")
        header_row = detail_title + 1
        row_music = next(
            r
            for r in range(header_row + 1, ws.max_row + 1)
            if ws.cell(row=r, column=2).value == "2602"
            and ws.cell(row=r, column=3).value == "音乐"
        )
        self.assertEqual(ws.cell(row=row_music, column=4).value, "正课")
        self.assertEqual(ws.cell(row=row_music, column=7).value, 1.0)

    def test_missing_report_group_raises(self):
        from common.exceptions import BusinessException

        self.slot_1.report_group = None
        self.slot_1.save(update_fields=["report_group"])
        with self.assertRaises(BusinessException):
            build_teacher_workbook(date(2026, 9, 7), date(2026, 9, 8))
