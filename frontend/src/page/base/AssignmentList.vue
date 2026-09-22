<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue"
import { NButton, NSelect, useMessage, type DataTableColumns } from "naive-ui"
import {
  reqAssignmentBulk,
  reqAssignmentClearClass,
  reqAssignmentList,
  reqClassList,
  reqSubjectList,
  reqTeacherList,
} from "@/api/base"
import type { SchoolClass, Subject, Teacher, TeachingAssignment } from "@/api/base/type"

const message = useMessage()
const subjects = ref<Subject[]>([])
const classes = ref<SchoolClass[]>([])
const teachers = ref<Teacher[]>([])
const assignments = ref<TeachingAssignment[]>([])
const loading = ref(false)
const clearClassId = ref<number | null>(null)

const teacherOptions = computed(() =>
  teachers.value.map((t) => ({
    label: `${t.name}（${t.subject_name}）`,
    value: t.id,
  })),
)

const mapping = computed(() => {
  const map: Record<string, number | null> = {}
  for (const a of assignments.value) {
    map[`${a.school_class}-${a.subject}`] = a.teacher
  }
  return map
})

async function load() {
  loading.value = true
  try {
    const [subs, cls, tea, asg] = await Promise.all([
      reqSubjectList(),
      reqClassList({ size: 500 }),
      reqTeacherList({ size: 500 }),
      reqAssignmentList({ size: 500 }),
    ])
    subjects.value = subs.data
    classes.value = cls.data.items
    teachers.value = tea.data.items
    assignments.value = asg.data.items
  } finally {
    loading.value = false
  }
}

async function setTeacher(subjectId: number, classId: number, teacherId: number | null) {
  await reqAssignmentBulk([
    { school_class: classId, subject: subjectId, teacher: teacherId },
  ])
  assignments.value = (await reqAssignmentList({ size: 500 })).data.items
}

async function clearClass() {
  if (!clearClassId.value) return message.warning("请先选择班级")
  const res = await reqAssignmentClearClass(clearClassId.value)
  message.success(`已取消 ${res.data.deleted} 条任课关系`)
  assignments.value = (await reqAssignmentList({ size: 500 })).data.items
}

const columns = computed<DataTableColumns<Subject>>(() => {
  const base: DataTableColumns<Subject> = [
    { title: "学科", key: "name", width: 100, fixed: "left" },
  ]
  for (const c of classes.value) {
    base.push({
      title: c.name,
      key: `class-${c.id}`,
      width: 200,
      render: (subject) =>
        h(NSelect, {
          value: mapping.value[`${c.id}-${subject.id}`] ?? null,
          options: teacherOptions.value,
          filterable: true,
          clearable: true,
          bordered: false,
          size: "small",
          placeholder: "未指定",
          style: "width: 100%",
          "onUpdate:value": (v: number | null) => setTeacher(subject.id, c.id, v),
        }),
    })
  }
  return base
})

onMounted(load)
</script>

<template>
  <div>
    <h3 class="page-title">任课关系（班级 × 学科 → 教师）</h3>
    <div class="toolbar">
      <n-button @click="load">刷新</n-button>
      <n-select
        v-model:value="clearClassId"
        :options="classes.map((c) => ({ label: c.name, value: c.id }))"
        placeholder="选择班级"
        style="width: 160px"
      />
      <n-button type="warning" ghost @click="clearClass">取消该班全部任课关系</n-button>
    </div>
    <n-data-table
      :columns="columns"
      :data="subjects"
      :loading="loading"
      :bordered="true"
      :single-line="false"
      :scroll-x="1400"
    />
  </div>
</template>
