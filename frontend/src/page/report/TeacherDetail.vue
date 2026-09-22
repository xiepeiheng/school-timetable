<script setup lang="ts">
import { h, onMounted, ref } from "vue"
import { type DataTableColumns } from "naive-ui"
import { reqTeacherList } from "@/api/base"
import type { Teacher } from "@/api/base/type"
import { reqTeacherDetail } from "@/api/timetable"
import type { TeacherDetailRow } from "@/api/timetable/type"
import { addDays, fmt, WEEKDAY_NAMES } from "@/utils/dates"

const teachers = ref<Teacher[]>([])
const rows = ref<TeacherDetailRow[]>([])
const selectedTeacher = ref<number | null>(null)
const range = ref<[string, string]>([fmt(new Date()), addDays(fmt(new Date()), 6)])
const loading = ref(false)

async function load() {
  if (!selectedTeacher.value || !range.value) return
  loading.value = true
  try {
    rows.value = (
      await reqTeacherDetail({
        teacher: selectedTeacher.value,
        start_date: range.value[0],
        end_date: range.value[1],
      })
    ).data
  } finally {
    loading.value = false
  }
}

const columns: DataTableColumns<TeacherDetailRow> = [
  { title: "日期", key: "date" },
  { title: "星期", key: "weekday", width: 80, render: (r) => WEEKDAY_NAMES[r.weekday - 1] },
  { title: "时间段", key: "time_slot_name", width: 90 },
  { title: "班级", key: "school_class_name", width: 100 },
  { title: "学科", key: "subject_name", width: 90 },
  { title: "权重", key: "weight", width: 80 },
  { title: "状态", key: "status", width: 90 },
  { title: "备注", key: "note" },
]

onMounted(async () => {
  teachers.value = (await reqTeacherList({ size: 500 })).data.items
  if (teachers.value.length) {
    selectedTeacher.value = teachers.value[0].id
    await load()
  }
})
</script>

<template>
  <div>
    <h3 class="page-title">教师课时明细</h3>
    <div class="toolbar">
      <n-select
        v-model:value="selectedTeacher"
        :options="teachers.map((t) => ({ label: t.name, value: t.id }))"
        filterable
        style="width: 160px"
        @update:value="load"
      />
      <n-date-picker
        v-model:formatted-value="range"
        type="daterange"
        value-format="yyyy-MM-dd"
        @update:formatted-value="load"
      />
      <n-button @click="load">查询</n-button>
      <span style="color: #888">共 {{ rows.length }} 条</span>
    </div>
    <n-data-table :columns="columns" :data="rows" :loading="loading" :bordered="true" />
  </div>
</template>
