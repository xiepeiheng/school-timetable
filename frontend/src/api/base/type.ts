export interface Subject {
  id: number
  name: string
  color: string
  sort_order: number
  is_main: boolean
  is_active: boolean
}

export interface Teacher {
  id: number
  name: string
  subject: number
  subject_name: string
  note: string
  is_cross_grade: boolean
  full_load_score: number
  is_active: boolean
}

export interface SchoolClass {
  id: number
  name: string
  grade: string
  homeroom_teacher: number | null
  homeroom_teacher_name: string
  sort_order: number
  is_key_class: boolean
  is_active: boolean
}

export interface TimeSlot {
  id: number
  name: string
  sort_order: number
  report_group: number | null
  report_group_name: string
  is_active: boolean
}

export interface ReportGroup {
  id: number
  kind: string
  kind_display: string
  coefficient: string
  sort_order: number
}

export interface Semester {
  id: number
  name: string
  start_date: string | null
  end_date: string | null
}

export interface TeachingAssignment {
  id: number
  school_class: number
  school_class_name: string
  subject: number
  subject_name: string
  teacher: number
  teacher_name: string
}
