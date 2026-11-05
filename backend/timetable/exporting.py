"""教师个人课表导出。

每个教师一个页签：每日课表、按节次/按学科统计、绩效系数计算。
教师页签之后是每个启用班级的课表；工作簿第一个页签是教师绩效汇总。
"""

from collections import defaultdict
from datetime import date, timedelta

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from common.exceptions import BusinessException
from timetable.models import CourseSession, ReportGroup, SchoolClass, Teacher, TimeSlot

WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]

TEACHING_SLOT_ORDER = [
    "早读",
    "一",
    "二",
    "三",
    "四",
    "五",
    "六",
    "七",
    "八",
    "晚一",
    "晚二",
    "晚三",
]

FLAG_FILL = {
    "swap": "FFE0B2",  # 换课：橙
    "substitute": "BBDEFB",  # 代课：蓝
    "abnormal": "FFCDD2",  # 异常：红
}
FLAG_LABEL = dict(CourseSession.Flag.choices)

CATEGORY_LABEL = dict(ReportGroup.Kind.choices)
KEY_CLASS_COEFFICIENT = 1.1
CROSS_GRADE_COEFFICIENT = 1.2
EXCESS_COEFFICIENT = 1.5

_THIN = Side(style="thin", color="999999")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
_EDIT_FILL = PatternFill("solid", fgColor="FFF2CC")
_CALC_FILL = PatternFill("solid", fgColor="EDEDED")


def _sheet_title(name: str) -> str:
    for ch in "[]:*?/\\":
        name = name.replace(ch, "_")
    return name[:31]


def _excel_sheet_ref(title: str, cell: str) -> str:
    safe = title.replace("'", "''")
    return f"'{safe}'!{cell}"


def _is_weekend(day: date) -> bool:
    return day.isoweekday() >= 6


def _write_class_sheet(ws, klass, days, slots, sess_map):
    """班级课表：行=日期，列=节次，格子=学科 - 教师。"""
    headers = ["日期", "星期"] + [s.name for s in slots]
    for col, head in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=head)
    ncols = len(headers)

    for i, day in enumerate(days):
        r = 2 + i
        ws.cell(row=r, column=1, value=f"{day.month}.{day.day}")
        ws.cell(row=r, column=2, value=f"周{WEEKDAY_CN[day.isoweekday() - 1]}")
        for j, slot in enumerate(slots):
            session = sess_map.get((day, slot.id))
            if not session:
                continue
            teacher_name = session.teacher.name if session.teacher else "未指定"
            ws.cell(
                row=r,
                column=3 + j,
                value=f"{session.subject.name} - {teacher_name}",
            )

    for r in range(1, 1 + len(days)):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = _BORDER
            cell.alignment = _CENTER
    for c in range(1, ncols + 1):
        ws.cell(row=1, column=c).font = Font(bold=True)

    ws.row_dimensions[1].height = 22
    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 6
    for c in range(3, ncols + 1):
        ws.column_dimensions[get_column_letter(c)].width = 15
    ws.freeze_panes = "C2"


def _write_stat_table(
    ws,
    start_row: int,
    title: str,
    headers: list[str],
    rows: list[tuple[str, list[int]]],
    column_totals: list[int],
) -> int:
    """写一张「行标签 × 分类」统计表，返回合计行行号。"""
    width = len(headers)
    ws.merge_cells(
        start_row=start_row,
        start_column=1,
        end_row=start_row,
        end_column=width,
    )
    title_cell = ws.cell(row=start_row, column=1, value=title)
    title_cell.font = Font(bold=True)
    title_cell.alignment = Alignment(horizontal="left", vertical="center")

    header_row = start_row + 1
    for col, head in enumerate(headers, start=1):
        ws.cell(row=header_row, column=col, value=head)

    for i, (label, values) in enumerate(rows):
        r = header_row + 1 + i
        ws.cell(row=r, column=1, value=label)
        for col, value in enumerate(values, start=2):
            ws.cell(row=r, column=col, value=value)
        ws.cell(row=r, column=width, value=sum(values))

    total_row = header_row + 1 + len(rows)
    ws.cell(row=total_row, column=1, value="合计")
    for col, value in enumerate(column_totals, start=2):
        ws.cell(row=total_row, column=col, value=value)
    ws.cell(row=total_row, column=width, value=sum(column_totals))

    for r in range(header_row, total_row + 1):
        for c in range(1, width + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = _BORDER
            cell.alignment = _CENTER
    for c in range(1, width + 1):
        ws.cell(row=header_row, column=c).font = Font(bold=True)
        ws.cell(row=total_row, column=c).font = Font(bold=True)
    return total_row


def _teacher_category_counts(sessions):
    workday_course = workday_study = weekend_course = weekend_study = 0
    for s in sessions:
        kind = s.time_slot.report_group.kind
        if _is_weekend(s.date):
            if kind == ReportGroup.Kind.COURSE:
                weekend_course += 1
            else:
                weekend_study += 1
        else:
            if kind == ReportGroup.Kind.COURSE:
                workday_course += 1
            else:
                workday_study += 1
    return {
        "workday_course": workday_course,
        "workday_study": workday_study,
        "weekend_course": weekend_course,
        "weekend_study": weekend_study,
        "total": workday_course + workday_study + weekend_course + weekend_study,
    }


def _write_coefficient_block(
    ws, teacher, sessions, start_row, base_coefficients, days
):
    """写参数区、按周工作量、按周系数明细和绩效结果。"""
    range_start, range_end = days[0], days[-1]
    weeks = []
    cur = range_start - timedelta(days=range_start.weekday())
    while cur <= range_end:
        week_end = cur + timedelta(days=6)
        inter_start = max(cur, range_start)
        inter_end = min(week_end, range_end)
        if inter_start <= inter_end:
            weeks.append(
                {
                    "start": cur,
                    "label": (
                        f"{inter_start.month}.{inter_start.day}"
                        f"~{inter_end.month}.{inter_end.day}"
                    ),
                }
            )
        cur += timedelta(days=7)
    week_starts = [w["start"] for w in weeks]

    week_counts = {
        week_start: {
            "workday_course": 0,
            "workday_study": 0,
            "weekend_course": 0,
            "weekend_study": 0,
        }
        for week_start in week_starts
    }
    for s in sessions:
        week_start = s.date - timedelta(days=s.date.weekday())
        counts = week_counts.get(week_start)
        if counts is None:
            continue
        kind = s.time_slot.report_group.kind
        prefix = "weekend" if _is_weekend(s.date) else "workday"
        suffix = "course" if kind == ReportGroup.Kind.COURSE else "study"
        counts[f"{prefix}_{suffix}"] += 1

    class_rows = sorted(
        {
            (
                s.school_class.sort_order,
                s.school_class.id,
                s.school_class.name,
                s.school_class.is_key_class,
            )
            for s in sessions
        }
    )
    subject_rows = sorted(
        {
            (s.subject.sort_order, s.subject.id, s.subject.name, s.subject.is_main)
            for s in sessions
        }
    )
    detail_counts: dict[tuple, int] = defaultdict(int)
    for s in sessions:
        week_start = s.date - timedelta(days=s.date.weekday())
        detail_counts[
            (
                week_start,
                s.school_class_id,
                s.subject_id,
                s.time_slot.report_group.kind,
            )
        ] += 1

    title_row = start_row
    ws.cell(row=title_row, column=1, value="绩效系数计算").font = Font(bold=True)

    params = [
        ("教师系数", CROSS_GRADE_COEFFICIENT if teacher.is_cross_grade else 1.0),
        ("满课系数", float(teacher.full_load_score)),
        ("超额倍数", EXCESS_COEFFICIENT),
        ("正课基准系数", base_coefficients[ReportGroup.Kind.COURSE]),
        ("自习基准系数", base_coefficients[ReportGroup.Kind.SELF_STUDY]),
    ]
    param_start = title_row + 1
    param_rows = {}
    for i, (label, value) in enumerate(params):
        r = param_start + i
        ws.cell(row=r, column=1, value=label)
        ws.cell(row=r, column=2, value=value).fill = _EDIT_FILL
        ws.cell(row=r, column=2).number_format = "0.00"
        param_rows[label] = r
        for c in (1, 2):
            ws.cell(row=r, column=c).border = _BORDER
            ws.cell(row=r, column=c).alignment = _CENTER

    weekly_title_row = param_start + len(params) + 1
    ws.cell(row=weekly_title_row, column=1, value="按周工作量（不满一周按一周）").font = Font(
        bold=True
    )
    weekly_headers = [
        "周次",
        "周一至周五课",
        "周一至周五自习",
        "周六日课",
        "周六日自习",
        "总课时",
        "系数合计（未计超额）",
        "满课系数",
        "超额系数",
        "最终绩效",
    ]
    weekly_header_row = weekly_title_row + 1
    for col, head in enumerate(weekly_headers, start=1):
        ws.cell(row=weekly_header_row, column=col, value=head)
    weekly_first_row = weekly_header_row + 1
    weekly_last_row = weekly_first_row + len(weeks) - 1

    detail_title_row = weekly_last_row + 2
    ws.cell(row=detail_title_row, column=1, value="系数明细（按周）").font = Font(
        bold=True
    )
    detail_headers = [
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
    ]
    header_row = detail_title_row + 1
    for col, head in enumerate(detail_headers, start=1):
        ws.cell(row=header_row, column=col, value=head)

    teacher_coef_cell = f"$B${param_rows['教师系数']}"
    course_base_cell = f"$B${param_rows['正课基准系数']}"
    study_base_cell = f"$B${param_rows['自习基准系数']}"
    threshold_cell = f"$B${param_rows['满课系数']}"
    excess_cell = f"$B${param_rows['超额倍数']}"

    first_detail_row = header_row + 1
    r = first_detail_row
    for week_start, week_label in [(w["start"], w["label"]) for w in weeks]:
        for _, class_id, class_name, is_key_class in class_rows:
            for _, subject_id, subject_name, is_main in subject_rows:
                for kind in (ReportGroup.Kind.COURSE, ReportGroup.Kind.SELF_STUDY):
                    count = detail_counts.get(
                        (week_start, class_id, subject_id, kind), 0
                    )
                    if not count:
                        continue
                    class_factor = (
                        KEY_CLASS_COEFFICIENT
                        if kind == ReportGroup.Kind.COURSE
                        and is_main
                        and is_key_class
                        else 1.0
                    )
                    ws.cell(row=r, column=1, value=week_label)
                    ws.cell(row=r, column=2, value=class_name)
                    ws.cell(row=r, column=3, value=subject_name)
                    ws.cell(row=r, column=4, value=CATEGORY_LABEL[kind])
                    ws.cell(row=r, column=5, value=count)
                    ws.cell(
                        row=r,
                        column=6,
                        value=(
                            f'=IF($D{r}="正课",{course_base_cell},{study_base_cell})'
                        ),
                    )
                    ws.cell(row=r, column=7, value=class_factor)
                    ws.cell(row=r, column=8, value=f"={teacher_coef_cell}")
                    ws.cell(row=r, column=9, value=f"=F{r}*G{r}*H{r}")
                    ws.cell(row=r, column=10, value=f"=E{r}*I{r}")
                    ws.cell(row=r, column=6).fill = _EDIT_FILL
                    ws.cell(row=r, column=7).fill = _EDIT_FILL
                    ws.cell(row=r, column=8).fill = _CALC_FILL
                    ws.cell(row=r, column=9).fill = _CALC_FILL
                    ws.cell(row=r, column=10).fill = _CALC_FILL
                    for c in (6, 7, 8, 9, 10):
                        ws.cell(row=r, column=c).number_format = "0.00"
                    r += 1
    detail_end_row = r - 1

    total_row = r
    ws.cell(row=total_row, column=1, value="合计")
    ws.cell(
        row=total_row,
        column=5,
        value=f"=SUM(E{first_detail_row}:E{detail_end_row})",
    )
    ws.cell(
        row=total_row,
        column=10,
        value=f"=SUM(J{first_detail_row}:J{detail_end_row})",
    )
    for c in range(1, 11):
        ws.cell(row=total_row, column=c).font = Font(bold=True)
        ws.cell(row=total_row, column=c).fill = _CALC_FILL

    for row in range(header_row, total_row + 1):
        for col in range(1, 11):
            cell = ws.cell(row=row, column=col)
            cell.border = _BORDER
            cell.alignment = _CENTER
    for col in range(1, 11):
        ws.cell(row=header_row, column=col).font = Font(bold=True)

    # 按周工作量：原始节数为静态值，系数/超额/最终绩效为公式。
    for i, week in enumerate(weeks):
        row = weekly_first_row + i
        counts = week_counts[week["start"]]
        total_count = sum(counts.values())
        ws.cell(row=row, column=1, value=week["label"])
        ws.cell(row=row, column=2, value=counts["workday_course"])
        ws.cell(row=row, column=3, value=counts["workday_study"])
        ws.cell(row=row, column=4, value=counts["weekend_course"])
        ws.cell(row=row, column=5, value=counts["weekend_study"])
        ws.cell(row=row, column=6, value=total_count)
        ws.cell(
            row=row,
            column=7,
            value=(
                f"=SUMIF($A${first_detail_row}:$A${detail_end_row},"
                f"$A{row},$J${first_detail_row}:$J${detail_end_row})"
            ),
        )
        ws.cell(row=row, column=8, value=f"={threshold_cell}")
        ws.cell(row=row, column=9, value=f"=MAX(0,G{row}-H{row})")
        ws.cell(
            row=row,
            column=10,
            value=f"=IF(G{row}<=H{row},G{row},H{row}+I{row}*{excess_cell})",
        )
        for c in (7, 8, 9, 10):
            ws.cell(row=row, column=c).number_format = "0.00"
            ws.cell(row=row, column=c).fill = _CALC_FILL

    for row in range(weekly_header_row, weekly_last_row + 1):
        for col in range(1, 11):
            cell = ws.cell(row=row, column=col)
            cell.border = _BORDER
            cell.alignment = _CENTER
    for col in range(1, 11):
        ws.cell(row=weekly_header_row, column=col).font = Font(bold=True)

    result_start = total_row + 2
    ws.cell(row=result_start, column=1, value="绩效结果").font = Font(bold=True)
    category_counts = _teacher_category_counts(sessions)
    results = [
        (
            "原始正课节数",
            category_counts["workday_course"] + category_counts["weekend_course"],
        ),
        (
            "原始自习节数",
            category_counts["workday_study"] + category_counts["weekend_study"],
        ),
        ("原始总节数", category_counts["total"]),
        (
            "系数合计（未计超额）",
            f"=SUM(J{first_detail_row}:J{detail_end_row})",
        ),
        ("周数", len(weeks)),
        (
            "按周绩效合计",
            f"=SUM(J{weekly_first_row}:J{weekly_last_row})",
        ),
    ]
    result_rows = {}
    for i, (label, value) in enumerate(results):
        row = result_start + 1 + i
        ws.cell(row=row, column=1, value=label)
        ws.cell(row=row, column=2, value=value)
        result_rows[label] = row
        for c in (1, 2):
            ws.cell(row=row, column=c).border = _BORDER
            ws.cell(row=row, column=c).alignment = _CENTER
        if i >= 3:
            ws.cell(row=row, column=2).fill = _CALC_FILL
    for i in range(3, len(results)):
        ws.cell(row=result_start + 1 + i, column=2).number_format = "0.00"

    return {
        "note_start": result_start + len(results) + 2,
        "final_row": result_rows["按周绩效合计"],
        **category_counts,
    }


def _write_teacher_sheet(
    ws, teacher, days, slots, sess_map, teacher_sessions, base_coefficients
):
    headers = ["日期", "星期"] + [s.name for s in slots] + ["合计"]
    for col, head in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=head)
    ncols = len(headers)
    slot_end_col = 2 + len(slots)
    total_col = slot_end_col + 1

    slot_counts = [0] * len(slots)
    flagged = []
    for i, day in enumerate(days):
        r = 2 + i
        ws.cell(row=r, column=1, value=f"{day.month}.{day.day}")
        ws.cell(row=r, column=2, value=f"周{WEEKDAY_CN[day.isoweekday() - 1]}")
        for j, slot in enumerate(slots):
            session = sess_map.get((day, slot.id))
            if not session:
                continue
            cell = ws.cell(row=r, column=3 + j, value=session.school_class.name)
            slot_counts[j] += 1
            if session.flag and session.flag != "normal":
                fill = FLAG_FILL.get(session.flag)
                if fill:
                    cell.fill = PatternFill("solid", fgColor=fill)
                flagged.append(
                    (
                        day,
                        slot.name,
                        session.school_class.name,
                        FLAG_LABEL.get(session.flag, ""),
                        session.note,
                    )
                )
        ws.cell(
            row=r,
            column=total_col,
            value=(
                f"=COUNTA({get_column_letter(3)}{r}:"
                f"{get_column_letter(slot_end_col)}{r})"
            ),
        )

    data_end = 1 + len(days)
    total_row = data_end + 1
    ws.cell(row=total_row, column=1, value="合计")
    for j in range(len(slots)):
        ws.cell(row=total_row, column=3 + j, value=slot_counts[j])
    ws.cell(row=total_row, column=total_col, value=sum(slot_counts))

    for r in range(1, total_row + 1):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = _BORDER
            cell.alignment = _CENTER
    for c in range(1, ncols + 1):
        ws.cell(row=1, column=c).font = Font(bold=True)
    for c in (1, total_col):
        ws.cell(row=total_row, column=c).font = Font(bold=True)

    summary = None
    if teacher_sessions:
        class_rows = sorted(
            {
                (s.school_class.sort_order, s.school_class.id, s.school_class.name)
                for s in teacher_sessions
            }
        )
        subject_rows = sorted(
            {
                (s.subject.sort_order, s.subject.id, s.subject.name)
                for s in teacher_sessions
            }
        )
        class_ids = [row[1] for row in class_rows]
        class_names = [row[2] for row in class_rows]
        subject_ids = [row[1] for row in subject_rows]
        subject_names = [row[2] for row in subject_rows]

        slot_counts_by_class: dict[tuple, int] = defaultdict(int)
        subject_counts: dict[tuple, int] = defaultdict(int)
        for s in teacher_sessions:
            slot_counts_by_class[(s.school_class_id, s.time_slot_id)] += 1
            subject_counts[(s.school_class_id, s.subject_id)] += 1

        slot_headers = ["班级"] + [slot.name for slot in slots] + ["合计"]
        slot_rows = [
            (
                class_name,
                [slot_counts_by_class[(class_id, slot.id)] for slot in slots],
            )
            for class_id, class_name in zip(class_ids, class_names)
        ]
        slot_totals = [
            sum(slot_counts_by_class[(class_id, slot.id)] for class_id in class_ids)
            for slot in slots
        ]

        subject_headers = ["班级"] + subject_names + ["合计"]
        subject_rows_data = [
            (
                class_name,
                [subject_counts[(class_id, subject_id)] for subject_id in subject_ids],
            )
            for class_id, class_name in zip(class_ids, class_names)
        ]
        subject_totals = [
            sum(subject_counts[(class_id, subject_id)] for class_id in class_ids)
            for subject_id in subject_ids
        ]

        end_row = _write_stat_table(
            ws,
            total_row + 2,
            "任课统计（按节次）",
            slot_headers,
            slot_rows,
            slot_totals,
        )
        end_row = _write_stat_table(
            ws,
            end_row + 2,
            "任课统计（按学科）",
            subject_headers,
            subject_rows_data,
            subject_totals,
        )
        summary = _write_coefficient_block(
            ws,
            teacher,
            teacher_sessions,
            end_row + 2,
            base_coefficients,
            days,
        )

    note_start = summary["note_start"] if summary else total_row + 2
    ws.cell(row=note_start, column=1, value="标注说明")
    for col, head in enumerate(["日期", "节次", "班级", "标记", "备注"], start=1):
        ws.cell(row=note_start + 1, column=col, value=head)
    for k, (day, slot, cls, flag, note) in enumerate(flagged):
        r = note_start + 2 + k
        ws.cell(row=r, column=1, value=f"{day.month}.{day.day}")
        ws.cell(row=r, column=2, value=slot)
        ws.cell(row=r, column=3, value=cls)
        ws.cell(row=r, column=4, value=flag)
        ws.cell(row=r, column=5, value=note or "")

    list_end = note_start + 1 + len(flagged)
    for r in range(note_start, list_end + 1):
        for c in range(1, 6):
            cell = ws.cell(row=r, column=c)
            cell.border = _BORDER
            cell.alignment = _CENTER
    for c in range(1, 6):
        ws.cell(row=note_start + 1, column=c).font = Font(bold=True)

    ws.row_dimensions[1].height = 22
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 6
    for c in range(3, ncols + 1):
        ws.column_dimensions[get_column_letter(c)].width = 10
    ws.freeze_panes = "C2"
    return summary


def _write_summary_sheet(ws, rows):
    headers = [
        "教师姓名",
        "周一至周五课",
        "周一至周五自习",
        "周六日课",
        "周六日自习",
        "总课时",
        "最终绩效",
    ]
    for col, head in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=head)

    for i, row in enumerate(rows):
        r = 2 + i
        ws.cell(row=r, column=1, value=row["teacher_name"])
        ws.cell(row=r, column=2, value=row["workday_course"])
        ws.cell(row=r, column=3, value=row["workday_study"])
        ws.cell(row=r, column=4, value=row["weekend_course"])
        ws.cell(row=r, column=5, value=row["weekend_study"])
        ws.cell(row=r, column=6, value=row["total"])
        ws.cell(
            row=r,
            column=7,
            value="="
            + _excel_sheet_ref(
                row["sheet_title"], f"$B${row['final_row']}"
            ),
        )
        ws.cell(row=r, column=7).number_format = "0.00"

    nrows = 1 + len(rows)
    for r in range(1, nrows + 1):
        for c in range(1, 8):
            cell = ws.cell(row=r, column=c)
            cell.border = _BORDER
            cell.alignment = _CENTER
    for c in range(1, 8):
        ws.cell(row=1, column=c).font = Font(bold=True)

    ws.row_dimensions[1].height = 24
    ws.column_dimensions["A"].width = 14
    for c in range(2, 8):
        ws.column_dimensions[get_column_letter(c)].width = 16
    ws.freeze_panes = "A2"


def build_teacher_workbook(start: date, end: date) -> openpyxl.Workbook:
    if start > end:
        raise BusinessException(message="起始日期不能晚于结束日期")

    base_coefficients = {
        kind: float(value)
        for kind, value in ReportGroup.objects.values_list(
            "kind", "coefficient"
        )
    }
    missing_groups = [
        ReportGroup.Kind.COURSE,
        ReportGroup.Kind.SELF_STUDY,
    ]
    missing_groups = [kind for kind in missing_groups if kind not in base_coefficients]
    if missing_groups:
        raise BusinessException(
            message="报告分组缺少：" + "、".join(missing_groups)
        )

    slots = list(
        TimeSlot.objects.filter(
            name__in=TEACHING_SLOT_ORDER, is_active=True
        ).select_related("report_group")
    )
    slots.sort(key=lambda s: TEACHING_SLOT_ORDER.index(s.name))
    missing_slots = [s.name for s in slots if s.report_group_id is None]
    if missing_slots:
        raise BusinessException(
            message="以下时间段未设置报告分组：" + "、".join(missing_slots)
        )
    slot_ids = [s.id for s in slots]

    all_sessions = list(
        CourseSession.objects.filter(date__range=(start, end)).select_related(
            "time_slot__report_group", "school_class", "subject", "teacher"
        )
    )
    missing_session_slots = sorted(
        {
            s.time_slot.name
            for s in all_sessions
            if s.time_slot.report_group_id is None
        }
    )
    if missing_session_slots:
        raise BusinessException(
            message="以下时间段未设置报告分组："
            + "、".join(missing_session_slots)
        )
    unsupported_slots = sorted(
        {s.time_slot.name for s in all_sessions if s.time_slot_id not in slot_ids}
    )
    if unsupported_slots:
        raise BusinessException(
            message="以下时间段不在教师个人课表导出范围："
            + "、".join(unsupported_slots)
        )

    sessions = [s for s in all_sessions if s.teacher_id]
    by_teacher: dict[int, dict] = defaultdict(dict)
    sessions_by_teacher: dict[int, list] = defaultdict(list)
    by_class: dict[int, dict] = defaultdict(dict)
    for s in all_sessions:
        by_class[s.school_class_id][(s.date, s.time_slot_id)] = s
    for s in sessions:
        by_teacher[s.teacher_id][(s.date, s.time_slot_id)] = s
        sessions_by_teacher[s.teacher_id].append(s)

    days: list[date] = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    used: set[str] = {"教师绩效汇总"}
    summary_rows = []

    for teacher in Teacher.objects.filter(is_active=True).select_related("subject"):
        title = _sheet_title(f"{teacher.subject.name}-{teacher.name}")
        base = title
        n = 1
        while title in used:
            n += 1
            title = _sheet_title(f"{base}({n})")
        used.add(title)
        ws = wb.create_sheet(title)
        result = _write_teacher_sheet(
            ws,
            teacher,
            days,
            slots,
            by_teacher.get(teacher.id, {}),
            sessions_by_teacher.get(teacher.id, []),
            base_coefficients,
        )
        if result:
            summary_rows.append(
                {
                    "teacher_name": teacher.name,
                    "sheet_title": title,
                    **result,
                }
            )

    for klass in SchoolClass.objects.filter(is_active=True).order_by(
        "sort_order", "id"
    ):
        title = _sheet_title(f"班级-{klass.name}")
        base = title
        n = 1
        while title in used:
            n += 1
            title = _sheet_title(f"{base}({n})")
        used.add(title)
        ws = wb.create_sheet(title)
        _write_class_sheet(ws, klass, days, slots, by_class.get(klass.id, {}))

    _write_summary_sheet(wb.create_sheet("教师绩效汇总", 0), summary_rows)
    return wb
