import { createRouter, createWebHistory } from "vue-router"
import { useStore } from "@/store"
import { reqMe } from "@/api/auth"

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("@/page/common/Login.vue"),
    },
    {
      path: "/",
      name: "index",
      component: () => import("@/page/Index.vue"),
      redirect: "/schedule",
      children: [
        {
          path: "schedule",
          name: "schedule",
          component: () => import("@/page/schedule/ScheduleEditor.vue"),
          meta: { title: "排课" },
        },
        {
          path: "templates",
          name: "templates",
          component: () => import("@/page/schedule/TemplateManage.vue"),
          meta: { title: "模板管理" },
        },
        {
          path: "class-timetable",
          name: "class-timetable",
          component: () => import("@/page/view/ClassTimetable.vue"),
          meta: { title: "班级课表" },
        },
        {
          path: "teacher-timetable",
          name: "teacher-timetable",
          component: () => import("@/page/view/TeacherTimetable.vue"),
          meta: { title: "教师课表" },
        },
        {
          path: "teacher-detail",
          name: "teacher-detail",
          component: () => import("@/page/report/TeacherDetail.vue"),
          meta: { title: "教师课时明细" },
        },
        {
          path: "teacher-summary",
          name: "teacher-summary",
          component: () => import("@/page/report/TeacherSummary.vue"),
          meta: { title: "教师课时汇总" },
        },
        {
          path: "base/subjects",
          name: "base-subjects",
          component: () => import("@/page/base/SubjectList.vue"),
          meta: { title: "学科" },
        },
        {
          path: "base/teachers",
          name: "base-teachers",
          component: () => import("@/page/base/TeacherList.vue"),
          meta: { title: "教师" },
        },
        {
          path: "base/classes",
          name: "base-classes",
          component: () => import("@/page/base/ClassList.vue"),
          meta: { title: "班级" },
        },
        {
          path: "base/time-slots",
          name: "base-time-slots",
          component: () => import("@/page/base/TimeSlotList.vue"),
          meta: { title: "时间段" },
        },
        {
          path: "base/semesters",
          name: "base-semesters",
          component: () => import("@/page/base/SemesterList.vue"),
          meta: { title: "学期" },
        },
        {
          path: "base/assignments",
          name: "base-assignments",
          component: () => import("@/page/base/AssignmentList.vue"),
          meta: { title: "任课关系" },
        },
        {
          path: "settings/lock",
          name: "settings-lock",
          component: () => import("@/page/settings/LockSetting.vue"),
          meta: { title: "锁定设置" },
        },
      ],
    },
    {
      path: "/:pathMatch(.*)*",
      name: "404",
      component: () => import("@/page/common/404.vue"),
    },
  ],
})

const publicPages = ["login", "404"]

router.beforeEach(async (to, _from, next) => {
  if (publicPages.includes(to.name as string)) return next()

  const token = localStorage.getItem("access_token")
  if (!token) return next({ name: "login" })

  const store = useStore()
  if (!store.userId) {
    try {
      const res = await reqMe()
      store.username = res.data.username
      store.userId = res.data.user_id
      store.isSuperuser = res.data.is_superuser
    } catch {
      store.logout()
      return next({ name: "login" })
    }
  }

  next()
})

export default router
