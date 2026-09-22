from datetime import date

from django.test import TestCase

from timetable import services
from timetable.models import (
    CourseSession,
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

    def test_locked_range_refused_entirely(self):
        from common.exceptions import BusinessException

        services.set_lock(date(2026, 9, 7))
        with self.assertRaises(BusinessException):
            services.generate_sessions(self.tpl, date(2026, 9, 7), date(2026, 9, 13))
        # 整体拒绝：周三及之后也不生成
        self.assertFalse(CourseSession.objects.exists())

    def test_range_after_lock_allowed(self):
        services.set_lock(date(2026, 9, 7))
        result = services.generate_sessions(self.tpl, date(2026, 9, 14), date(2026, 9, 20))
        self.assertGreater(result["created"], 0)


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

    def test_copy_day_rejects_locked_target(self):
        services.set_lock(date(2026, 9, 9))
        from common.exceptions import BusinessException

        with self.assertRaises(BusinessException):
            services.copy_day(date(2026, 9, 7), date(2026, 9, 9))

    def test_clear_range_refused_when_overlaps_lock(self):
        from common.exceptions import BusinessException

        services.set_lock(date(2026, 9, 8))
        with self.assertRaises(BusinessException):
            services.clear_range(date(2026, 9, 7), date(2026, 9, 9))
        # 整体拒绝：周一记录未被删除
        self.assertTrue(
            CourseSession.objects.filter(date=date(2026, 9, 7)).exists()
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

    def test_sync_class(self):
        result = services.sync_class(date(2026, 9, 7), self.c1.id, [self.c2.id])
        self.assertEqual(result["copied"], 2)
        self.assertEqual(
            CourseSession.objects.filter(
                date=date(2026, 9, 7), school_class=self.c2
            ).count(),
            2,
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


class SummaryTest(ServiceTestBase):
    def _add(self, day, slot):
        services.bulk_upsert_sessions(
            [
                {
                    "date": day,
                    "time_slot": slot.id,
                    "school_class": self.c1.id,
                    "subject": self.chinese.id,
                    "teacher": self.t_ma.id,
                }
            ]
        )

    def test_weighted_summary_uses_snapshot(self):
        self._add(date(2026, 9, 7), self.slot_early)  # weight 1
        self._add(date(2026, 9, 7), self.slot_4)  # weight 2
        data = services.teacher_summary(date(2026, 9, 1), date(2026, 9, 30))
        row = next(t for t in data["teachers"] if t["teacher"] == self.t_ma.id)
        # 1*1 + 1*2 = 3
        self.assertEqual(row["total"], "3.00")

    def test_changing_slot_weight_does_not_change_history(self):
        self._add(date(2026, 9, 7), self.slot_4)  # 快照权重 2
        self.slot_4.weight = 5
        self.slot_4.save()
        data = services.teacher_summary(date(2026, 9, 1), date(2026, 9, 30))
        row = next(t for t in data["teachers"] if t["teacher"] == self.t_ma.id)
        self.assertEqual(row["total"], "2.00")  # 历史不变

        self._add(date(2026, 9, 8), self.slot_4)  # 新记录用新权重 5
        data2 = services.teacher_summary(date(2026, 9, 1), date(2026, 9, 30))
        row2 = next(t for t in data2["teachers"] if t["teacher"] == self.t_ma.id)
        self.assertEqual(row2["total"], "7.00")
