from rest_framework.routers import DefaultRouter

from timetable.views import (
    CourseSessionViewSet,
    ReportViewSet,
    ScheduleLockViewSet,
    ScheduleTemplateViewSet,
    SchoolClassViewSet,
    SemesterViewSet,
    SubjectViewSet,
    TeacherViewSet,
    TeachingAssignmentViewSet,
    TemplateEntryViewSet,
    TimeSlotViewSet,
)

router = DefaultRouter()
router.register(r"semesters", SemesterViewSet, basename="semester")
router.register(r"subjects", SubjectViewSet, basename="subject")
router.register(r"teachers", TeacherViewSet, basename="teacher")
router.register(r"classes", SchoolClassViewSet, basename="class")
router.register(r"time-slots", TimeSlotViewSet, basename="time-slot")
router.register(
    r"teaching-assignments", TeachingAssignmentViewSet, basename="teaching-assignment"
)
router.register(r"templates", ScheduleTemplateViewSet, basename="template")
router.register(r"template-entries", TemplateEntryViewSet, basename="template-entry")
router.register(r"sessions", CourseSessionViewSet, basename="session")
router.register(r"lock", ScheduleLockViewSet, basename="lock")
router.register(r"reports", ReportViewSet, basename="report")

urlpatterns = router.urls
