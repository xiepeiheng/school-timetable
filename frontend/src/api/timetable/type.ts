export interface ScheduleTemplate {
  id: number
  name: string
  note: string
  is_default: boolean
  created_at: string
  entry_count: number
  class_count: number
}

export interface TemplateEntry {
  id: number
  template: number
  school_class: number
  school_class_name: string
  weekday: number
  time_slot: number
  time_slot_name: string
  subject: number
  subject_name: string
}

export interface CourseSession {
  id: number
  date: string
  time_slot: number
  time_slot_name: string
  school_class: number
  school_class_name: string
  subject: number
  subject_name: string
  teacher: number | null
  teacher_name: string
  status: string
  source: string
  note: string
}

export interface ScheduleLock {
  locked_through: string | null
  updated_at?: string
}

export interface SlotInfo {
  id: number
  name: string
  sort_order?: number
  weight?: string
}

export interface ClassTimetableRes {
  slots: SlotInfo[]
  sessions: {
    date: string
    weekday: number
    time_slot: number
    subject: number
    subject_name: string
    teacher: number | null
    teacher_name: string
    status: string
    note: string
  }[]
}

export interface TeacherTimetableRes {
  slots: SlotInfo[]
  sessions: {
    date: string
    weekday: number
    time_slot: number
    time_slot_name: string
    school_class: number
    school_class_name: string
    subject: number
    subject_name: string
    note: string
  }[]
  conflicts: {
    date: string
    time_slot: number
    items: TeacherTimetableRes["sessions"]
  }[]
}

export interface TeacherDetailRow {
  date: string
  weekday: number
  time_slot: number
  time_slot_name: string
  weight: string
  school_class: number
  school_class_name: string
  subject: number
  subject_name: string
  status: string
  note: string
}

export interface TeacherSummaryRes {
  slots: { id: number; name: string; weight: string }[]
  teachers: {
    teacher: number
    teacher_name: string
    subject_name: string
    counts: Record<string, number>
    total: string
  }[]
}
