import http from "@/axios"
import type { PaginatedData, ResponseData } from "@/api/common_type"
import type {
  SchoolClass,
  Semester,
  Subject,
  Teacher,
  TeachingAssignment,
  TimeSlot,
} from "./type"

// ── 学科（不分页） ──
export const reqSubjectList = (params?: { is_active?: number }) =>
  http.get<ResponseData<Subject[]>>("/subjects/", { params })
export const reqSubjectCreate = (data: Partial<Subject>) =>
  http.post<ResponseData<Subject>>("/subjects/", data)
export const reqSubjectUpdate = (id: number, data: Partial<Subject>) =>
  http.patch<ResponseData<Subject>>(`/subjects/${id}/`, data)
export const reqSubjectDelete = (id: number) =>
  http.delete<ResponseData<null>>(`/subjects/${id}/`)

// ── 教师（分页） ──
export const reqTeacherList = (params?: {
  page?: number
  size?: number
  is_active?: number
}) => http.get<ResponseData<PaginatedData<Teacher>>>("/teachers/", { params })
export const reqTeacherCreate = (data: Partial<Teacher>) =>
  http.post<ResponseData<Teacher>>("/teachers/", data)
export const reqTeacherUpdate = (id: number, data: Partial<Teacher>) =>
  http.patch<ResponseData<Teacher>>(`/teachers/${id}/`, data)
export const reqTeacherDelete = (id: number) =>
  http.delete<ResponseData<null>>(`/teachers/${id}/`)

// ── 班级（分页） ──
export const reqClassList = (params?: {
  page?: number
  size?: number
  is_active?: number
}) => http.get<ResponseData<PaginatedData<SchoolClass>>>("/classes/", { params })
export const reqClassCreate = (data: Partial<SchoolClass>) =>
  http.post<ResponseData<SchoolClass>>("/classes/", data)
export const reqClassUpdate = (id: number, data: Partial<SchoolClass>) =>
  http.patch<ResponseData<SchoolClass>>(`/classes/${id}/`, data)
export const reqClassDelete = (id: number) =>
  http.delete<ResponseData<null>>(`/classes/${id}/`)

// ── 时间段（不分页） ──
export const reqTimeSlotList = (params?: { is_active?: number }) =>
  http.get<ResponseData<TimeSlot[]>>("/time-slots/", { params })
export const reqTimeSlotCreate = (data: Partial<TimeSlot>) =>
  http.post<ResponseData<TimeSlot>>("/time-slots/", data)
export const reqTimeSlotUpdate = (id: number, data: Partial<TimeSlot>) =>
  http.patch<ResponseData<TimeSlot>>(`/time-slots/${id}/`, data)
export const reqTimeSlotDelete = (id: number) =>
  http.delete<ResponseData<null>>(`/time-slots/${id}/`)
export const reqTimeSlotReorder = (ids: number[]) =>
  http.post<ResponseData<null>>("/time-slots/reorder/", { ids })

// ── 学期（不分页） ──
export const reqSemesterList = () =>
  http.get<ResponseData<Semester[]>>("/semesters/")
export const reqSemesterCreate = (data: Partial<Semester>) =>
  http.post<ResponseData<Semester>>("/semesters/", data)
export const reqSemesterUpdate = (id: number, data: Partial<Semester>) =>
  http.patch<ResponseData<Semester>>(`/semesters/${id}/`, data)
export const reqSemesterDelete = (id: number) =>
  http.delete<ResponseData<null>>(`/semesters/${id}/`)

// ── 任课关系（分页） ──
export const reqAssignmentList = (params?: { page?: number; size?: number }) =>
  http.get<ResponseData<PaginatedData<TeachingAssignment>>>(
    "/teaching-assignments/",
    { params },
  )
export const reqAssignmentCreate = (data: {
  school_class: number
  subject: number
  teacher: number
}) => http.post<ResponseData<TeachingAssignment>>("/teaching-assignments/", data)
export const reqAssignmentUpdate = (
  id: number,
  data: { teacher: number },
) => http.patch<ResponseData<TeachingAssignment>>(`/teaching-assignments/${id}/`, data)
export const reqAssignmentDelete = (id: number) =>
  http.delete<ResponseData<null>>(`/teaching-assignments/${id}/`)
export const reqAssignmentBulk = (
  items: { school_class: number; subject: number; teacher: number | null }[],
) => http.post<ResponseData<null>>("/teaching-assignments/bulk/", items)
export const reqAssignmentClearClass = (school_class: number) =>
  http.post<ResponseData<{ deleted: number }>>(
    "/teaching-assignments/clear-class/",
    { school_class },
  )
