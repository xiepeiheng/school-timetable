from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import action

from common.exceptions import BusinessException, NotFoundException
from common.response import success_response
from timetable import services
from timetable.models import (
    CourseSession,
    ScheduleTemplate,
    SchoolClass,
    Semester,
    Subject,
    Teacher,
    TeachingAssignment,
    TemplateEntry,
    TimeSlot,
)
from timetable.serializers import (
    ApplyTemplateSerializer,
    ClearClassAssignmentsSerializer,
    ClearRangeSerializer,
    CopyDaySerializer,
    CourseSessionBulkWriteItemSerializer,
    CourseSessionReadSerializer,
    CourseSessionWriteSerializer,
    CreateFromWeekSerializer,
    ReportQuerySerializer,
    ScheduleLockSerializer,
    ScheduleTemplateReadSerializer,
    ScheduleTemplateWriteSerializer,
    SchoolClassReadSerializer,
    SchoolClassWriteSerializer,
    SemesterSerializer,
    SubjectSerializer,
    SyncClassSerializer,
    TeacherReadSerializer,
    TeacherWriteSerializer,
    TeachingAssignmentBulkItemSerializer,
    TeachingAssignmentReadSerializer,
    TeachingAssignmentWriteSerializer,
    TemplateDuplicateSerializer,
    TemplateEntryBulkItemSerializer,
    TemplateEntryReadSerializer,
    TemplateEntryWriteSerializer,
    TimeSlotReorderSerializer,
    TimeSlotSerializer,
)


class ActiveFilterMixin:
    """支持 ?is_active=1/0 过滤。"""

    def get_queryset(self):
        qs = super().get_queryset()
        value = self.request.query_params.get("is_active")
        if value in ("1", "true", "True"):
            qs = qs.filter(is_active=True)
        elif value in ("0", "false", "False"):
            qs = qs.filter(is_active=False)
        return qs


class SoftDeleteMixin:
    """有 is_active 的模型删除即停用；其余硬删除。"""

    def perform_destroy(self, instance):
        if hasattr(instance, "is_active"):
            instance.is_active = False
            instance.save(update_fields=["is_active"])
        else:
            instance.delete()


class SemesterViewSet(viewsets.ModelViewSet):
    queryset = Semester.objects.all()
    serializer_class = SemesterSerializer
    pagination_class = None


class SubjectViewSet(SoftDeleteMixin, ActiveFilterMixin, viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    pagination_class = None


class TeacherViewSet(SoftDeleteMixin, ActiveFilterMixin, viewsets.ModelViewSet):
    queryset = Teacher.objects.select_related("subject")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return TeacherWriteSerializer
        return TeacherReadSerializer


class SchoolClassViewSet(SoftDeleteMixin, ActiveFilterMixin, viewsets.ModelViewSet):
    queryset = SchoolClass.objects.select_related("homeroom_teacher")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return SchoolClassWriteSerializer
        return SchoolClassReadSerializer


class TimeSlotViewSet(ActiveFilterMixin, viewsets.ModelViewSet):
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    pagination_class = None

    def perform_destroy(self, instance):
        # 停用时间段 = 软删除，并清掉它在所有模板中的条目
        services.purge_template_entries_for_slot(instance.id)
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    def perform_update(self, serializer):
        was_active = serializer.instance.is_active
        instance = serializer.save()
        if was_active and not instance.is_active:
            services.purge_template_entries_for_slot(instance.id)

    @action(detail=False, methods=["post"])
    def reorder(self, request):
        serializer = TimeSlotReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        for index, slot_id in enumerate(ids):
            TimeSlot.objects.filter(id=slot_id).update(sort_order=index)
        return success_response(message="排序已更新")


class TeachingAssignmentViewSet(viewsets.ModelViewSet):
    queryset = TeachingAssignment.objects.select_related(
        "school_class", "subject", "teacher"
    )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return TeachingAssignmentWriteSerializer
        return TeachingAssignmentReadSerializer

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        serializer = TeachingAssignmentBulkItemSerializer(
            data=request.data if isinstance(request.data, list) else [],
            many=True,
        )
        serializer.is_valid(raise_exception=True)
        for item in serializer.validated_data:
            if item["teacher"]:
                TeachingAssignment.objects.update_or_create(
                    school_class_id=item["school_class"],
                    subject_id=item["subject"],
                    defaults={"teacher_id": item["teacher"]},
                )
            else:
                TeachingAssignment.objects.filter(
                    school_class_id=item["school_class"],
                    subject_id=item["subject"],
                ).delete()
        return success_response(message="任课关系已更新")

    @action(detail=False, methods=["post"], url_path="clear-class")
    def clear_class(self, request):
        serializer = ClearClassAssignmentsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deleted, _ = TeachingAssignment.objects.filter(
            school_class_id=serializer.validated_data["school_class"]
        ).delete()
        return success_response(
            data={"deleted": deleted}, message="已取消该班全部任课关系"
        )


class ScheduleTemplateViewSet(viewsets.ModelViewSet):
    queryset = ScheduleTemplate.objects.annotate(
        entry_count=Count("entries", distinct=True),
        class_count=Count("entries__school_class", distinct=True),
    ).order_by("-is_default", "id")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ScheduleTemplateWriteSerializer
        return ScheduleTemplateReadSerializer

    def perform_create(self, serializer):
        obj = serializer.save()
        if obj.is_default:
            ScheduleTemplate.objects.exclude(pk=obj.pk).update(is_default=False)

    def perform_update(self, serializer):
        obj = serializer.save()
        if obj.is_default:
            ScheduleTemplate.objects.exclude(pk=obj.pk).update(is_default=False)

    @action(detail=False, methods=["post"], url_path="create-from-week")
    def create_from_week(self, request):
        serializer = CreateFromWeekSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        template = services.create_template_from_week(
            name=data["name"],
            start=data["start_date"],
            end=data["end_date"],
            note=data.get("note", ""),
            is_default=data.get("is_default", False),
        )
        template = self.get_queryset().get(pk=template.pk)
        return success_response(
            data=ScheduleTemplateReadSerializer(template).data,
            message="模板已保存",
        )

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        source = self.get_object()
        serializer = TemplateDuplicateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new = services.duplicate_template(
            source, serializer.validated_data.get("name", "")
        )
        new = self.get_queryset().get(pk=new.pk)
        return success_response(
            data=ScheduleTemplateReadSerializer(new).data, message="模板已复制"
        )

    @action(detail=False, methods=["post"])
    def apply(self, request):
        serializer = ApplyTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            template = ScheduleTemplate.objects.get(pk=data["template"])
        except ScheduleTemplate.DoesNotExist:
            raise NotFoundException(message="模板不存在")
        result = services.generate_sessions(
            template=template,
            start=data["start_date"],
            end=data["end_date"],
            overwrite=data.get("overwrite", True),
        )
        return success_response(data=result, message="排课完成")


class TemplateEntryViewSet(viewsets.ModelViewSet):
    queryset = TemplateEntry.objects.select_related(
        "school_class", "time_slot", "subject"
    )

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get("template"):
            qs = qs.filter(template_id=params["template"])
        if params.get("school_class"):
            qs = qs.filter(school_class_id=params["school_class"])
        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return TemplateEntryWriteSerializer
        return TemplateEntryReadSerializer

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        serializer = TemplateEntryBulkItemSerializer(
            data=request.data if isinstance(request.data, list) else [], many=True
        )
        serializer.is_valid(raise_exception=True)
        result = services.bulk_upsert_template_entries(serializer.validated_data)
        return success_response(data=result, message="模板已保存")


class CourseSessionViewSet(viewsets.ModelViewSet):
    queryset = CourseSession.objects.select_related(
        "time_slot", "school_class", "subject", "teacher"
    )

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        if params.get("school_class"):
            qs = qs.filter(school_class_id=params["school_class"])
        if params.get("teacher"):
            qs = qs.filter(teacher_id=params["teacher"])
        if params.get("time_slot"):
            qs = qs.filter(time_slot_id=params["time_slot"])
        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return CourseSessionWriteSerializer
        return CourseSessionReadSerializer

    def perform_destroy(self, instance):
        if services.is_locked(instance.date):
            from common.exceptions import BusinessException

            raise BusinessException(message="该日期已被锁定，不可删除")
        instance.delete()

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        serializer = CourseSessionBulkWriteItemSerializer(
            data=request.data if isinstance(request.data, list) else [], many=True
        )
        serializer.is_valid(raise_exception=True)
        result = services.bulk_upsert_sessions(serializer.validated_data)
        return success_response(data=result, message="已保存")

    @action(detail=False, methods=["post"])
    def clear(self, request):
        serializer = ClearRangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = services.clear_range(
            start=data["start_date"],
            end=data["end_date"],
            school_class_ids=data.get("school_classes") or None,
            time_slot_ids=data.get("time_slots") or None,
        )
        return success_response(data=result, message="已清空")

    @action(detail=False, methods=["post"], url_path="copy-day")
    def copy_day(self, request):
        serializer = CopyDaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = services.copy_day(
            source=data["source_date"],
            target=data["target_date"],
            school_class_ids=data.get("school_classes") or None,
            time_slot_ids=data.get("time_slots") or None,
        )
        return success_response(data=result, message="已复制")

    @action(detail=False, methods=["post"], url_path="sync-class")
    def sync_class(self, request):
        serializer = SyncClassSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = services.sync_class(
            source_date=data["source_date"],
            source_class_id=data["source_class"],
            target_class_ids=data.get("target_classes") or None,
            time_slot_ids=data.get("time_slots") or None,
        )
        return success_response(data=result, message="已同步")


class ScheduleLockViewSet(viewsets.ViewSet):
    def list(self, request):
        lock = services.get_lock()
        return success_response(data={"locked_through": lock})

    def create(self, request):
        serializer = ScheduleLockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lock = services.set_lock(serializer.validated_data.get("locked_through"))
        return success_response(
            data={"locked_through": lock.locked_through}, message="锁定已更新"
        )

    @action(detail=False, methods=["delete"])
    def clear(self, request):
        services.set_lock(None)
        return success_response(message="锁定已取消")


class ReportViewSet(viewsets.ViewSet):
    @action(detail=False, methods=["get"], url_path="class-timetable")
    def class_timetable(self, request):
        serializer = ReportQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        params = request.query_params
        if not params.get("school_class"):
            return success_response(data=None, message="缺少班级参数")
        result = services.class_timetable(
            int(params["school_class"]), data["start_date"], data["end_date"]
        )
        return success_response(data=result)

    @action(detail=False, methods=["get"], url_path="teacher-timetable")
    def teacher_timetable(self, request):
        serializer = ReportQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        params = request.query_params
        if not params.get("teacher"):
            return success_response(data=None, message="缺少教师参数")
        result = services.teacher_timetable(
            int(params["teacher"]), data["start_date"], data["end_date"]
        )
        return success_response(data=result)

    @action(detail=False, methods=["get"], url_path="teacher-detail")
    def teacher_detail(self, request):
        serializer = ReportQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        params = request.query_params
        if not params.get("teacher"):
            return success_response(data=None, message="缺少教师参数")
        result = services.teacher_detail(
            int(params["teacher"]), data["start_date"], data["end_date"]
        )
        return success_response(data=result)

    @action(detail=False, methods=["get"], url_path="teacher-summary")
    def teacher_summary(self, request):
        serializer = ReportQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = services.teacher_summary(data["start_date"], data["end_date"])
        return success_response(data=result)
