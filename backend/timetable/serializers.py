from rest_framework import serializers

from timetable.models import (
    CourseSession,
    ScheduleLock,
    ScheduleTemplate,
    SchoolClass,
    Semester,
    Subject,
    Teacher,
    TeachingAssignment,
    TemplateEntry,
    TimeSlot,
)

# ────────────────────────── 基础资料 ──────────────────────────


class SemesterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Semester
        fields = ["id", "name", "start_date", "end_date"]


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ["id", "name", "color", "sort_order", "is_active"]


class TeacherReadSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = Teacher
        fields = [
            "id",
            "name",
            "subject",
            "subject_name",
            "note",
            "is_active",
        ]


class TeacherWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Teacher
        fields = ["id", "name", "subject", "note", "is_active"]


class SchoolClassReadSerializer(serializers.ModelSerializer):
    homeroom_teacher_name = serializers.CharField(
        source="homeroom_teacher.name", read_only=True, default=""
    )

    class Meta:
        model = SchoolClass
        fields = [
            "id",
            "name",
            "grade",
            "homeroom_teacher",
            "homeroom_teacher_name",
            "sort_order",
            "is_active",
        ]


class SchoolClassWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolClass
        fields = [
            "id",
            "name",
            "grade",
            "homeroom_teacher",
            "sort_order",
            "is_active",
        ]


class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = ["id", "name", "sort_order", "weight", "is_active"]


class TimeSlotReorderSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField())


class TeachingAssignmentReadSerializer(serializers.ModelSerializer):
    school_class_name = serializers.CharField(
        source="school_class.name", read_only=True
    )
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.name", read_only=True)

    class Meta:
        model = TeachingAssignment
        fields = [
            "id",
            "school_class",
            "school_class_name",
            "subject",
            "subject_name",
            "teacher",
            "teacher_name",
        ]


class TeachingAssignmentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeachingAssignment
        fields = ["id", "school_class", "subject", "teacher"]


class TeachingAssignmentBulkItemSerializer(serializers.Serializer):
    school_class = serializers.IntegerField()
    subject = serializers.IntegerField()
    teacher = serializers.IntegerField(allow_null=True)


class ClearClassAssignmentsSerializer(serializers.Serializer):
    school_class = serializers.IntegerField()


# ────────────────────────── 模板 ──────────────────────────


class TemplateEntryReadSerializer(serializers.ModelSerializer):
    school_class_name = serializers.CharField(
        source="school_class.name", read_only=True
    )
    time_slot_name = serializers.CharField(source="time_slot.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = TemplateEntry
        fields = [
            "id",
            "template",
            "school_class",
            "school_class_name",
            "weekday",
            "time_slot",
            "time_slot_name",
            "subject",
            "subject_name",
        ]


class TemplateEntryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateEntry
        fields = ["id", "template", "school_class", "weekday", "time_slot", "subject"]


class TemplateEntryBulkItemSerializer(serializers.Serializer):
    template = serializers.IntegerField()
    school_class = serializers.IntegerField()
    weekday = serializers.IntegerField(min_value=1, max_value=7)
    time_slot = serializers.IntegerField()
    subject = serializers.IntegerField(allow_null=True, required=False)


class TemplateDuplicateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False, allow_blank=True)


class ScheduleTemplateReadSerializer(serializers.ModelSerializer):
    entry_count = serializers.IntegerField(read_only=True)
    class_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ScheduleTemplate
        fields = [
            "id",
            "name",
            "note",
            "is_default",
            "created_at",
            "entry_count",
            "class_count",
        ]


class ScheduleTemplateWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleTemplate
        fields = ["id", "name", "note", "is_default"]


class CreateFromWeekSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    note = serializers.CharField(required=False, allow_blank=True, default="")
    start_date = serializers.DateField(help_text="必须为周一")
    end_date = serializers.DateField(help_text="必须为周日")
    is_default = serializers.BooleanField(default=False)


class ApplyTemplateSerializer(serializers.Serializer):
    template = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    overwrite = serializers.BooleanField(default=True)


# ────────────────────────── 课程记录 ──────────────────────────


class CourseSessionReadSerializer(serializers.ModelSerializer):
    time_slot_name = serializers.CharField(source="time_slot.name", read_only=True)
    school_class_name = serializers.CharField(
        source="school_class.name", read_only=True
    )
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    teacher_name = serializers.CharField(
        source="teacher.name", read_only=True, default=""
    )

    class Meta:
        model = CourseSession
        fields = [
            "id",
            "date",
            "time_slot",
            "time_slot_name",
            "school_class",
            "school_class_name",
            "subject",
            "subject_name",
            "teacher",
            "teacher_name",
            "weight",
            "status",
            "source",
            "note",
        ]


class CourseSessionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseSession
        fields = [
            "id",
            "date",
            "time_slot",
            "school_class",
            "subject",
            "teacher",
            "status",
            "source",
            "note",
        ]


class CourseSessionBulkWriteItemSerializer(serializers.Serializer):
    date = serializers.DateField()
    time_slot = serializers.IntegerField()
    school_class = serializers.IntegerField()
    subject = serializers.IntegerField(allow_null=True)
    teacher = serializers.IntegerField(allow_null=True, required=False)
    status = serializers.CharField(required=False)
    note = serializers.CharField(required=False, allow_blank=True)


class ClearRangeSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    school_classes = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    time_slots = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )


class CopyDaySerializer(serializers.Serializer):
    source_date = serializers.DateField()
    target_date = serializers.DateField()
    school_classes = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    time_slots = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )


class SyncClassSerializer(serializers.Serializer):
    source_date = serializers.DateField()
    source_class = serializers.IntegerField()
    target_classes = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    time_slots = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )


class ScheduleLockSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleLock
        fields = ["locked_through", "updated_at"]
        read_only_fields = ["updated_at"]


# ────────────────────────── 报表 ──────────────────────────


class ReportQuerySerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    school_class = serializers.IntegerField(required=False, allow_null=True)
    teacher = serializers.IntegerField(required=False, allow_null=True)
