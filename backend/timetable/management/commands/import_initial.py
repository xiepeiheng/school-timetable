"""从现有 Excel 导入初始数据。

用法：
    python manage.py import_initial
    python manage.py import_initial --week-start 2026-09-07
    python manage.py import_initial --dir /path/to/files

读取：
    - 课程表.xls                          → 学科 + 教师
    - 高一课程表9月定.xlsx                → 班级/班主任/时间段/任课关系/模板课表

导入后会自动用模板生成 --week-start 所在整周的实际课程记录。
"""

from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import openpyxl
import xlrd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from timetable import services
from timetable.models import (
    ScheduleTemplate,
    SchoolClass,
    Subject,
    Teacher,
    TeachingAssignment,
    TemplateEntry,
    TimeSlot,
)

SUBJECT_ORDER = [
    "语文",
    "数学",
    "英语",
    "物理",
    "化学",
    "生物",
    "政治",
    "历史",
    "地理",
    "音乐",
    "体育",
    "舞蹈",
    "美术",
]

SUBJECT_CHAR = {
    "语": "语文",
    "数": "数学",
    "英": "英语",
    "物": "物理",
    "化": "化学",
    "生": "生物",
    "政": "政治",
    "历": "历史",
    "地": "地理",
    "音": "音乐",
    "体": "体育",
    "舞": "舞蹈",
    "美": "美术",
}

# 课表网格行的顺序（相对 早读 行的偏移）
SLOT_ROWS = [
    ("早读", 0),
    ("早饭", 1),
    ("早自主", 2),
    ("一", 3),
    ("二", 4),
    ("三", 5),
    ("四", 6),
    ("午休", 7),
    ("五", 8),
    ("六", 9),
    ("七", 10),
    ("八", 11),
    ("晚饭", 12),
    ("晚一", 13),
    ("晚二", 14),
    ("晚三", 15),
    ("晚四", 16),
]

TEACHING_SLOTS = {"早读", "一", "二", "三", "四", "五", "六", "七", "八", "晚一", "晚二", "晚三"}

# 每个班的 (名称, 标签列, 起始列, 早读行号)
CLASS_LAYOUT = [
    ("2601", 1, 2, 6),
    ("2602", 9, 10, 6),
    ("2603", 17, 18, 6),
    ("2604", 25, 26, 6),
    ("2605", 1, 2, 26),
    ("2606", 9, 10, 26),
    ("2607", 17, 18, 26),
    ("2608", 25, 26, 26),
    ("2609", 33, 34, 26),
]

FOOTER_ROW = {6: 23, 26: 43}


class Command(BaseCommand):
    help = "从 files/ 下的 Excel 导入初始数据"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            default=str(Path(settings.BASE_DIR).parent / "files"),
            help="Excel 文件所在目录",
        )
        parser.add_argument(
            "--week-start",
            default="2026-09-07",
            help="生成实际课程记录的基准周一（YYYY-MM-DD）",
        )

    def handle(self, *args, **options):
        base = Path(options["dir"])
        teachers_file = base / "课程表.xls"
        timetable_file = base / "高一课程表9月定.xlsx"
        if not teachers_file.exists() or not timetable_file.exists():
            raise CommandError(f"找不到 Excel 文件，请检查目录：{base}")

        week_start = date.fromisoformat(options["week_start"])
        if week_start.isoweekday() != 1:
            raise CommandError("--week-start 必须是周一")

        with transaction.atomic():
            subjects = self._import_subjects_teachers(teachers_file)
            self._import_timetable(timetable_file, subjects)
            self._generate_week(week_start)

        self.stdout.write(self.style.SUCCESS("导入完成"))

    # ── 学科 + 教师 ──
    def _import_subjects_teachers(self, path: Path) -> dict:
        wb = xlrd.open_workbook(str(path))
        ws = wb.sheet_by_name("教师表")
        subjects: dict[str, Subject] = {}
        order = 0
        for r in range(1, ws.nrows):
            subject_name = str(ws.cell_value(r, 0)).strip()
            teacher_name = str(ws.cell_value(r, 1)).strip()
            if not teacher_name:
                continue
            subject, _ = Subject.objects.get_or_create(
                name=subject_name, defaults={"sort_order": order}
            )
            if subject_name not in subjects:
                subjects[subject_name] = subject
                order += 1
            Teacher.objects.get_or_create(
                name=teacher_name, defaults={"subject": subject}
            )
        self.stdout.write(f"学科 {Subject.objects.count()}，教师 {Teacher.objects.count()}")
        return subjects

    # ── 班级 / 时间段 / 任课关系 / 模板 / 课表 ──
    def _import_timetable(self, path: Path, subjects: dict):
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.active

        def cell(row, col):
            return ws.cell(row=row, column=col).value

        # 时间段框架（含不排课的行）
        for index, (name, _offset) in enumerate(SLOT_ROWS):
            TimeSlot.objects.get_or_create(
                name=name, defaults={"sort_order": index, "weight": 1}
            )
        slots = {s.name: s for s in TimeSlot.objects.all()}

        known_teachers = list(Teacher.objects.values_list("name", flat=True))

        # 班级
        classes: dict[str, SchoolClass] = {}
        for order, (class_name, label_col, _start_col, early_row) in enumerate(
            CLASS_LAYOUT
        ):
            header = cell(early_row - 2, label_col) or ""
            homeroom = self._parse_homeroom(str(header))
            homeroom_teacher = None
            if homeroom:
                homeroom_teacher = Teacher.objects.filter(name=homeroom).first()
            klass, _ = SchoolClass.objects.update_or_create(
                name=class_name,
                defaults={
                    "grade": "高一1部",
                    "homeroom_teacher": homeroom_teacher,
                    "sort_order": order,
                },
            )
            classes[class_name] = klass
        self.stdout.write(f"班级 {SchoolClass.objects.count()}")

        template, _ = ScheduleTemplate.objects.get_or_create(
            name="9月标准模板", defaults={"is_default": True}
        )
        TemplateEntry.objects.filter(template=template).delete()

        entries = []
        total_cells = 0
        for class_name, label_col, start_col, early_row in CLASS_LAYOUT:
            klass = classes[class_name]
            footer_row = FOOTER_ROW[early_row]
            names = self._parse_footer(
                str(cell(footer_row, label_col) or ""), known_teachers
            )

            # 任课关系
            for subject_name, teacher_name in zip(SUBJECT_ORDER, names):
                if not teacher_name:
                    continue
                teacher = Teacher.objects.filter(name=teacher_name).first()
                if not teacher:
                    continue
                TeachingAssignment.objects.update_or_create(
                    school_class=klass,
                    subject=subjects[subject_name],
                    defaults={"teacher": teacher},
                )

            # 模板条目
            for day in range(7):
                weekday = day + 1
                for slot_name, offset in SLOT_ROWS:
                    if slot_name not in TEACHING_SLOTS:
                        continue
                    value = cell(early_row + offset, start_col + day)
                    if not value:
                        continue
                    subject_name = SUBJECT_CHAR.get(str(value).strip())
                    if not subject_name:
                        continue
                    entries.append(
                        TemplateEntry(
                            template=template,
                            school_class=klass,
                            weekday=weekday,
                            time_slot=slots[slot_name],
                            subject=subjects[subject_name],
                        )
                    )
                    total_cells += 1

        TemplateEntry.objects.bulk_create(entries, ignore_conflicts=True)
        self.stdout.write(
            f"任课关系 {TeachingAssignment.objects.count()}，模板条目 {total_cells}"
        )

    def _generate_week(self, week_start: date):
        template = ScheduleTemplate.objects.filter(is_default=True).first()
        if not template:
            template = ScheduleTemplate.objects.first()
        if not template:
            self.stdout.write(self.style.WARNING("没有模板，跳过生成课程记录"))
            return
        end = week_start + timedelta(days=6)
        result = services.generate_sessions(template, week_start, end, overwrite=True)
        self.stdout.write(
            f"生成课程记录：{result['created']} 条（{week_start} ~ {end}）"
        )

    # ── 辅助 ──
    @staticmethod
    def _parse_homeroom(header: str) -> str:
        import re

        match = re.search(r"\d{4}班主任[：:]\s*([\u4e00-\u9fa5]+)", header)
        return match.group(1) if match else ""

    @staticmethod
    def _parse_footer(text: str, known_names: list[str]) -> list:
        """按学科顺序从底部名单中提取教师姓名（容忍缺失空格）。"""
        remaining = text
        result = []
        for _ in SUBJECT_ORDER:
            best = None
            best_index = None
            for name in known_names:
                index = remaining.find(name)
                if index != -1 and (best_index is None or index < best_index):
                    best_index = index
                    best = name
            if best is None:
                result.append(None)
                continue
            result.append(best)
            remaining = remaining[best_index + len(best):]
        return result
