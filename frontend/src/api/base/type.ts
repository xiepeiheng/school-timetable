export interface Subject {
  id: number
  name: string
  color: string
  sort_order: number
  is_active: boolean
}

export interface Teacher {
  id: number
  name: string
  subject: number
  subject_name: string
  note: string
  is_active: boolean
}

export interface SchoolClass {
  id: number
  name: string
  grade: string
  homeroom_teacher: number | null
  homeroom_teacher_name: string
  sort_order: number
  is_active: boolean
}

export interface TimeSlot {
  id: number
  name: string
  sort_order: number
  weight: string
  is_active: boolean
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
