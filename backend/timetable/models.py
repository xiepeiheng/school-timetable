from django.db import models


class Semester(models.Model):
    """学期：仅用于日期选择器预填，不做业务约束。"""

    name = models.CharField(max_length=100)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date", "id"]

    def __str__(self):
        return self.name


class Subject(models.Model):
    """学科，如 语文/数学。"""

    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=20, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class Teacher(models.Model):
    """教师。一人一科；学科仅作默认提示，实际以便用记录/任课关系为准。"""

    name = models.CharField(max_length=50)
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="teachers"
    )
    note = models.CharField(max_length=200, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["subject__sort_order", "id"]

    def __str__(self):
        return self.name


class SchoolClass(models.Model):
    """班级。"""

    name = models.CharField(max_length=50, unique=True)
    grade = models.CharField(max_length=50, blank=True, default="")
    homeroom_teacher = models.ForeignKey(
        Teacher,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="homeroom_classes",
    )
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class TimeSlot(models.Model):
    """时间段（课表的一行）。只表示排序，不绑定具体时刻。权重默认 1。"""

    name = models.CharField(max_length=50)
    sort_order = models.PositiveIntegerField(default=0)
    weight = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class TeachingAssignment(models.Model):
    """任课关系：班级 × 学科 → 教师。仅作排课时的默认老师来源。"""

    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="assignments"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="assignments"
    )
    teacher = models.ForeignKey(
        Teacher, on_delete=models.PROTECT, related_name="assignments"
    )

    class Meta:
        unique_together = ("school_class", "subject")
        ordering = ["school_class__sort_order", "subject__sort_order", "id"]

    def __str__(self):
        return f"{self.school_class}-{self.subject}->{self.teacher}"


class ScheduleTemplate(models.Model):
    """排课模板：一组条目，覆盖全体班级、完整周一~周日。"""

    name = models.CharField(max_length=100)
    note = models.CharField(max_length=300, blank=True, default="")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "id"]

    def __str__(self):
        return self.name


class TemplateEntry(models.Model):
    """模板条目：模板 + 班级 + 星期 + 时间段 → 学科。"""

    template = models.ForeignKey(
        ScheduleTemplate, on_delete=models.CASCADE, related_name="entries"
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="template_entries"
    )
    weekday = models.PositiveSmallIntegerField(help_text="1=周一 ... 7=周日")
    time_slot = models.ForeignKey(
        TimeSlot, on_delete=models.CASCADE, related_name="template_entries"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="template_entries"
    )

    class Meta:
        unique_together = ("template", "school_class", "weekday", "time_slot")
        ordering = [
            "school_class__sort_order",
            "weekday",
            "time_slot__sort_order",
        ]

    def __str__(self):
        return f"{self.school_class} 周{self.weekday} {self.time_slot} {self.subject}"


class CourseSession(models.Model):
    """实际课程记录：历史的唯一真相。"""

    class Status(models.TextChoices):
        NORMAL = "normal", "正常"
        SUSPENDED = "suspended", "停课"
        EXAM = "exam", "考试"
        SELF_STUDY = "self_study", "自习"

    class Source(models.TextChoices):
        TEMPLATE = "template", "模板生成"
        MANUAL = "manual", "手动"

    date = models.DateField()
    time_slot = models.ForeignKey(
        TimeSlot, on_delete=models.PROTECT, related_name="sessions"
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.PROTECT, related_name="sessions"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="sessions"
    )
    teacher = models.ForeignKey(
        Teacher,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sessions",
    )
    weight = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1,
        help_text="写入时对时间段权重的快照，改时间段权重不影响历史",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NORMAL
    )
    source = models.CharField(
        max_length=20, choices=Source.choices, default=Source.MANUAL
    )
    note = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        unique_together = ("date", "time_slot", "school_class")
        ordering = ["date", "school_class__sort_order", "time_slot__sort_order"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["teacher", "date"]),
        ]

    def __str__(self):
        return f"{self.date} {self.school_class} {self.time_slot} {self.subject}"


class ScheduleLock(models.Model):
    """全局锁定设置：该日期及之前的课程记录不可改删。"""

    locked_through = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "锁定设置"
        verbose_name_plural = "锁定设置"
