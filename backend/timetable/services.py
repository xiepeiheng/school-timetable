"""排课/批量/统计 的显式服务层。

跨多表集体操作集中在此，由 ViewSet 在同一请求内显式调用（不使用信号）。
"""

from collections import defaultdict
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, Sum

from common.exceptions import BusinessException
from timetable.models import (
    CourseSession,
    ScheduleLock,
    ScheduleTemplate,
    SchoolClass,
    TeachingAssignment,
    TemplateEntry,
    TimeSlot,
)


def daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def get_lock() -> date | None:
    lock = ScheduleLock.objects.first()
    return lock.locked_through if lock else None


def set_lock(value: date | None) -> ScheduleLock:
    lock = ScheduleLock.objects.first()
    if lock is None:
        lock = ScheduleLock.objects.create(locked_through=value)
    else:
        lock.locked_through = value
        lock.save(update_fields=["locked_through", "updated_at"])
    return lock


def is_locked(target: date, lock: date | None = None) -> bool:
    lock = get_lock() if lock is None else lock
    return bool(lock and target <= lock)


def assert_range_unlocked(start: date, end: date, action: str = "操作") -> None:
    """批量操作整段执行：只要范围与锁定区间有交集就整体拒绝，避免半覆盖造成混乱。"""
    lock = get_lock()
    if lock and start <= lock:
        raise BusinessException(
            message=f"所选范围包含已锁定日期（锁定至 {lock}），{action}已取消"
        )


# ────────────────────────── 生成 / 模板 ──────────────────────────


@transaction.atomic
def generate_sessions(
    template: ScheduleTemplate,
    start: date,
    end: date,
    overwrite: bool = True,
) -> dict:
    """按模板为日期区间生成课程记录。范围涉及锁定日期则整体拒绝。"""
    assert_range_unlocked(start, end, action="一键排课")
    assignments = {
        (a.school_class_id, a.subject_id): a.teacher_id
        for a in TeachingAssignment.objects.all()
    }
    by_weekday: dict[int, list[TemplateEntry]] = defaultdict(list)
    for entry in template.entries.select_related("time_slot").filter(
        time_slot__is_active=True
    ):
        by_weekday[entry.weekday].append(entry)

    created = updated = skipped = 0
    for day in daterange(start, end):
        if overwrite:
            CourseSession.objects.filter(date=day).delete()
        for entry in by_weekday.get(day.isoweekday(), []):
            teacher_id = assignments.get((entry.school_class_id, entry.subject_id))
            defaults = {
                "subject": entry.subject,
                "teacher_id": teacher_id,
                "weight": entry.time_slot.weight,
                "source": CourseSession.Source.TEMPLATE,
                "status": CourseSession.Status.NORMAL,
            }
            key = {
                "date": day,
                "time_slot": entry.time_slot,
                "school_class": entry.school_class,
            }
            if overwrite:
                CourseSession.objects.update_or_create(**key, defaults=defaults)
                created += 1
            else:
                _, is_created = CourseSession.objects.get_or_create(
                    **key, defaults=defaults
                )
                if is_created:
                    created += 1
                else:
                    skipped += 1
    return {
        "created": created,
        "skipped": skipped,
        "locked_days": 0,
        "updated": updated,
    }


@transaction.atomic
def create_template_from_week(
    name: str,
    start: date,
    end: date,
    note: str = "",
    is_default: bool = False,
) -> ScheduleTemplate:
    """把某一整周（周一~周日）的课程记录另存为模板。"""
    if (end - start).days != 6 or start.isoweekday() != 1:
        raise BusinessException(message="范围必须是完整的周一~周日（起始日为周一，跨度 7 天）")

    template = ScheduleTemplate.objects.create(
        name=name, note=note, is_default=is_default
    )
    if is_default:
        ScheduleTemplate.objects.exclude(pk=template.pk).update(is_default=False)

    sessions = CourseSession.objects.filter(
        date__range=(start, end), time_slot__is_active=True
    ).select_related("school_class", "time_slot", "subject")
    entries = [
        TemplateEntry(
            template=template,
            school_class=s.school_class,
            weekday=s.date.isoweekday(),
            time_slot=s.time_slot,
            subject=s.subject,
        )
        for s in sessions
    ]
    TemplateEntry.objects.bulk_create(entries, ignore_conflicts=True)
    return template


@transaction.atomic
def duplicate_template(source: ScheduleTemplate, name: str = "") -> ScheduleTemplate:
    new = ScheduleTemplate.objects.create(
        name=name or f"{source.name} 副本", note=source.note
    )
    entries = [
        TemplateEntry(
            template=new,
            school_class=e.school_class,
            weekday=e.weekday,
            time_slot=e.time_slot,
            subject=e.subject,
        )
        for e in source.entries.all()
    ]
    TemplateEntry.objects.bulk_create(entries, ignore_conflicts=True)
    return new


@transaction.atomic
def bulk_upsert_template_entries(items: list[dict]) -> dict:
    """按格子批量写入/清空模板条目。subject 为空表示清空该格。"""
    created = updated = deleted = 0
    for item in items:
        key = {
            "template_id": item["template"],
            "school_class_id": item["school_class"],
            "weekday": item["weekday"],
            "time_slot_id": item["time_slot"],
        }
        subject_id = item.get("subject")
        if not subject_id:
            deleted += TemplateEntry.objects.filter(**key).delete()[0]
            continue
        _, is_created = TemplateEntry.objects.update_or_create(
            **key, defaults={"subject_id": subject_id}
        )
        if is_created:
            created += 1
        else:
            updated += 1
    return {"created": created, "updated": updated, "deleted": deleted}


def purge_template_entries_for_slot(slot_id: int) -> int:
    """时间段停用时，删除它在所有模板中的条目。"""
    deleted, _ = TemplateEntry.objects.filter(time_slot_id=slot_id).delete()
    return deleted


# ────────────────────────── 批量操作 ──────────────────────────


@transaction.atomic
def clear_range(
    start: date,
    end: date,
    school_class_ids: list[int] | None = None,
    time_slot_ids: list[int] | None = None,
) -> dict:
    assert_range_unlocked(start, end, action="清空")
    qs = CourseSession.objects.filter(date__range=(start, end))
    if school_class_ids:
        qs = qs.filter(school_class_id__in=school_class_ids)
    if time_slot_ids:
        qs = qs.filter(time_slot_id__in=time_slot_ids)
    deleted, _ = qs.delete()
    return {"deleted": deleted}


@transaction.atomic
def copy_day(
    source: date,
    target: date,
    school_class_ids: list[int] | None = None,
    time_slot_ids: list[int] | None = None,
) -> dict:
    if is_locked(target):
        raise BusinessException(message="目标日期已被锁定，不可修改")

    source_qs = CourseSession.objects.filter(date=source)
    if school_class_ids:
        source_qs = source_qs.filter(school_class_id__in=school_class_ids)
    if time_slot_ids:
        source_qs = source_qs.filter(time_slot_id__in=time_slot_ids)
    source_sessions = list(source_qs)

    target_qs = CourseSession.objects.filter(date=target)
    if school_class_ids:
        target_qs = target_qs.filter(school_class_id__in=school_class_ids)
    if time_slot_ids:
        target_qs = target_qs.filter(time_slot_id__in=time_slot_ids)
    target_qs.delete()

    new_objs = [
        CourseSession(
            date=target,
            time_slot=s.time_slot,
            school_class=s.school_class,
            subject=s.subject,
            teacher=s.teacher,
            weight=s.weight,
            status=s.status,
            source=CourseSession.Source.MANUAL,
            note=s.note,
        )
        for s in source_sessions
    ]
    CourseSession.objects.bulk_create(new_objs)
    return {"copied": len(new_objs)}


@transaction.atomic
def sync_class(
    source_date: date,
    source_class_id: int,
    target_class_ids: list[int] | None = None,
    time_slot_ids: list[int] | None = None,
) -> dict:
    """把某班某日的课表同步到同日其他班（挖孔后全体执行）。"""
    if is_locked(source_date):
        raise BusinessException(message="该日期已被锁定，不可修改")

    source_qs = CourseSession.objects.filter(
        date=source_date, school_class_id=source_class_id
    )
    if time_slot_ids:
        source_qs = source_qs.filter(time_slot_id__in=time_slot_ids)
    source_sessions = list(source_qs)

    if target_class_ids:
        target_classes = list(
            SchoolClass.objects.filter(id__in=target_class_ids)
        )
    else:
        target_classes = list(
            SchoolClass.objects.exclude(id=source_class_id)
        )
    if not target_classes:
        raise BusinessException(message="没有可同步的目标班级")

    # 目标班同日、同一组时间段先清空，再按源班铺开
    conflicts = CourseSession.objects.filter(
        date=source_date, school_class__in=target_classes
    )
    if time_slot_ids:
        conflicts = conflicts.filter(time_slot_id__in=time_slot_ids)
    conflicts.delete()

    new_objs = [
        CourseSession(
            date=source_date,
            time_slot=s.time_slot,
            school_class=target,
            subject=s.subject,
            teacher=s.teacher,
            weight=s.weight,
            status=s.status,
            source=CourseSession.Source.MANUAL,
            note=s.note,
        )
        for target in target_classes
        for s in source_sessions
    ]
    CourseSession.objects.bulk_create(new_objs)
    return {"copied": len(new_objs), "target_classes": len(target_classes)}


@transaction.atomic
def bulk_upsert_sessions(items: list[dict]) -> dict:
    """按格子批量写入/清空课程记录。subject 为空表示清空该格。"""
    lock = get_lock()
    slot_weight = dict(TimeSlot.objects.values_list("id", "weight"))
    created = updated = deleted = 0
    for item in items:
        day = item["date"]
        if is_locked(day, lock):
            raise BusinessException(message=f"{day} 已被锁定，不可修改")
        key = {
            "date": day,
            "time_slot_id": item["time_slot"],
            "school_class_id": item["school_class"],
        }
        subject_id = item.get("subject")
        if not subject_id:
            deleted += CourseSession.objects.filter(**key).delete()[0]
            continue
        defaults = {
            "subject_id": subject_id,
            "teacher_id": item.get("teacher"),
            "weight": slot_weight.get(item["time_slot"], 1),
            "status": item.get("status") or CourseSession.Status.NORMAL,
            "note": item.get("note") or "",
            "source": CourseSession.Source.MANUAL,
        }
        _, is_created = CourseSession.objects.update_or_create(
            **key, defaults=defaults
        )
        if is_created:
            created += 1
        else:
            updated += 1
    return {"created": created, "updated": updated, "deleted": deleted}


# ────────────────────────── 报表 ──────────────────────────


def teacher_detail(teacher_id: int, start: date, end: date) -> list[dict]:
    qs = (
        CourseSession.objects.filter(
            teacher_id=teacher_id, date__range=(start, end)
        )
        .exclude(status=CourseSession.Status.SUSPENDED)
        .select_related("time_slot", "school_class", "subject")
        .order_by("date", "time_slot__sort_order")
    )
    return [
        {
            "date": s.date,
            "weekday": s.date.isoweekday(),
            "time_slot": s.time_slot_id,
            "time_slot_name": s.time_slot.name,
            "weight": str(s.weight),
            "school_class": s.school_class_id,
            "school_class_name": s.school_class.name,
            "subject": s.subject_id,
            "subject_name": s.subject.name,
            "status": s.status,
            "note": s.note,
        }
        for s in qs
    ]


def teacher_summary(start: date, end: date) -> dict:
    """每列显示次数；合计 = Σ(每条记录的权重快照)，因此改时间段权重不影响历史。"""
    slots = list(TimeSlot.objects.all().order_by("sort_order", "id"))
    slot_ids = [s.id for s in slots]

    rows = (
        CourseSession.objects.filter(date__range=(start, end))
        .exclude(status=CourseSession.Status.SUSPENDED)
        .values("teacher_id", "time_slot_id")
        .annotate(cnt=Count("id"), wsum=Sum("weight"))
    )

    from timetable.models import Teacher

    teachers = {t.id: t for t in Teacher.objects.select_related("subject").all()}
    per_teacher: dict[int, dict] = {}
    for row in rows:
        tid = row["teacher_id"]
        if tid is None:
            continue
        entry = per_teacher.setdefault(tid, {"counts": {}, "wsum": {}})
        sid = row["time_slot_id"]
        entry["counts"][sid] = row["cnt"]
        entry["wsum"][sid] = row["wsum"] or 0

    result = []
    for tid, data in per_teacher.items():
        teacher = teachers.get(tid)
        counts = {sid: data["counts"].get(sid, 0) for sid in slot_ids}
        total = sum(data["wsum"].values(), start=0)
        result.append(
            {
                "teacher": tid,
                "teacher_name": teacher.name if teacher else "",
                "subject_name": teacher.subject.name if teacher else "",
                "counts": counts,
                "total": f"{total:.2f}",
            }
        )
    result.sort(key=lambda x: x["teacher_name"])
    return {
        "slots": [
            {"id": s.id, "name": s.name, "weight": str(s.weight)}
            for s in slots
        ],
        "teachers": result,
    }


def class_timetable(class_id: int, start: date, end: date) -> dict:
    qs = (
        CourseSession.objects.filter(
            school_class_id=class_id, date__range=(start, end)
        )
        .select_related("time_slot", "subject", "teacher")
        .order_by("date", "time_slot__sort_order")
    )
    return {
        "slots": list(
            TimeSlot.objects.all()
            .order_by("sort_order", "id")
            .values("id", "name", "sort_order", "weight")
        ),
        "sessions": [
            {
                "date": s.date,
                "weekday": s.date.isoweekday(),
                "time_slot": s.time_slot_id,
                "subject": s.subject_id,
                "subject_name": s.subject.name,
                "teacher": s.teacher_id,
                "teacher_name": s.teacher.name if s.teacher else "",
                "status": s.status,
                "note": s.note,
            }
            for s in qs
        ],
    }


def teacher_timetable(teacher_id: int, start: date, end: date) -> dict:
    qs = (
        CourseSession.objects.filter(
            teacher_id=teacher_id, date__range=(start, end)
        )
        .exclude(status=CourseSession.Status.SUSPENDED)
        .select_related("time_slot", "school_class", "subject")
        .order_by("date", "time_slot__sort_order")
    )
    sessions = [
        {
            "date": s.date,
            "weekday": s.date.isoweekday(),
            "time_slot": s.time_slot_id,
            "time_slot_name": s.time_slot.name,
            "school_class": s.school_class_id,
            "school_class_name": s.school_class.name,
            "subject": s.subject_id,
            "subject_name": s.subject.name,
            "note": s.note,
        }
        for s in qs
    ]
    # 冲突检测：同一日期同一时间段出现在多个班
    bucket: dict[tuple, list[dict]] = defaultdict(list)
    for s in sessions:
        bucket[(s["date"], s["time_slot"])].append(s)
    conflicts = [
        {"date": k[0], "time_slot": k[1], "items": v}
        for k, v in bucket.items()
        if len(v) > 1
    ]
    return {
        "slots": list(
            TimeSlot.objects.all()
            .order_by("sort_order", "id")
            .values("id", "name", "sort_order", "weight")
        ),
        "sessions": sessions,
        "conflicts": conflicts,
    }
