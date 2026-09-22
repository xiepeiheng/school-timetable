import http from "@/axios"
import type { PaginatedData, ResponseData } from "@/api/common_type"
import type {
  ClassTimetableRes,
  CourseSession,
  ScheduleLock,
  ScheduleTemplate,
  TeacherDetailRow,
  TeacherSummaryRes,
  TeacherTimetableRes,
  TemplateEntry,
} from "./type"

// ── 模板 ──
export const reqTemplateList = () =>
  http.get<ResponseData<PaginatedData<ScheduleTemplate>>>("/templates/")
export const reqTemplateCreate = (data: {
  name: string
  note?: string
  is_default?: boolean
}) => http.post<ResponseData<ScheduleTemplate>>("/templates/", data)
export const reqTemplateUpdate = (
  id: number,
  data: { name?: string; note?: string; is_default?: boolean },
) => http.patch<ResponseData<ScheduleTemplate>>(`/templates/${id}/`, data)
export const reqTemplateDuplicate = (id: number, data: { name?: string } = {}) =>
  http.post<ResponseData<ScheduleTemplate>>(`/templates/${id}/duplicate/`, data)
export const reqTemplateDelete = (id: number) =>
  http.delete<ResponseData<null>>(`/templates/${id}/`)

// ── 模板条目 ──
export const reqTemplateEntryList = (params: {
  template: number
  school_class?: number
}) =>
  http.get<ResponseData<PaginatedData<TemplateEntry>>>("/template-entries/", {
    params: { ...params, size: 500 },
  })
export const reqTemplateEntryBulk = (
  items: {
    template: number
    school_class: number
    weekday: number
    time_slot: number
    subject: number | null
  }[],
) =>
  http.post<ResponseData<{ created: number; updated: number; deleted: number }>>(
    "/template-entries/bulk/",
    items,
  )
export const reqTemplateCreateFromWeek = (data: {
  name: string
  note?: string
  start_date: string
  end_date: string
  is_default?: boolean
}) =>
  http.post<ResponseData<ScheduleTemplate>>(
    "/templates/create-from-week/",
    data,
  )
export const reqTemplateApply = (data: {
  template: number
  start_date: string
  end_date: string
  overwrite?: boolean
}) =>
  http.post<ResponseData<{ created: number; skipped: number; locked_days: number }>>(
    "/templates/apply/",
    data,
  )

// ── 课程记录 ──
export const reqSessionList = (params: {
  date_from?: string
  date_to?: string
  school_class?: number
  teacher?: number
  page?: number
  size?: number
}) =>
  http.get<ResponseData<PaginatedData<CourseSession>>>("/sessions/", { params })

export const reqSessionBulk = (
  items: {
    date: string
    time_slot: number
    school_class: number
    subject: number | null
    teacher?: number | null
    note?: string
  }[],
) => http.post<ResponseData<{ created: number; updated: number; deleted: number }>>(
  "/sessions/bulk/",
  items,
)

export const reqSessionClear = (data: {
  start_date: string
  end_date: string
  school_classes?: number[]
  time_slots?: number[]
}) => http.post<ResponseData<{ deleted: number }>>("/sessions/clear/", data)

export const reqSessionCopyDay = (data: {
  source_date: string
  target_date: string
  school_classes?: number[]
  time_slots?: number[]
}) => http.post<ResponseData<{ copied: number }>>("/sessions/copy-day/", data)

export const reqSessionSyncClass = (data: {
  source_date: string
  source_class: number
  target_classes?: number[]
  time_slots?: number[]
}) =>
  http.post<ResponseData<{ copied: number; target_classes: number }>>(
    "/sessions/sync-class/",
    data,
  )

// ── 锁定 ──
export const reqLockGet = () =>
  http.get<ResponseData<{ locked_through: string | null }>>("/lock/")
export const reqLockSet = (locked_through: string | null) =>
  http.post<ResponseData<{ locked_through: string | null }>>("/lock/", {
    locked_through,
  })
export const reqLockClear = () => http.delete<ResponseData<null>>("/lock/clear/")

// ── 报表 ──
export const reqClassTimetable = (params: {
  school_class: number
  start_date: string
  end_date: string
}) =>
  http.get<ResponseData<ClassTimetableRes>>("/reports/class-timetable/", {
    params,
  })

export const reqTeacherTimetable = (params: {
  teacher: number
  start_date: string
  end_date: string
}) =>
  http.get<ResponseData<TeacherTimetableRes>>("/reports/teacher-timetable/", {
    params,
  })

export const reqTeacherDetail = (params: {
  teacher: number
  start_date: string
  end_date: string
}) =>
  http.get<ResponseData<TeacherDetailRow[]>>("/reports/teacher-detail/", {
    params,
  })

export const reqTeacherSummary = (params: {
  start_date: string
  end_date: string
}) =>
  http.get<ResponseData<TeacherSummaryRes>>("/reports/teacher-summary/", {
    params,
  })
