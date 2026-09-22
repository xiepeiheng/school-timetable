<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { type DataTableColumns } from "naive-ui"
import { reqTeacherSummary } from "@/api/timetable"
import type { TeacherSummaryRes } from "@/api/timetable/type"
import { addDays, fmt } from "@/utils/dates"

type Row = TeacherSummaryRes["teachers"][number]

const slots = ref<TeacherSummaryRes["slots"]>([])
const rows = ref<Row[]>([])
const range = ref<[string, string]>([fmt(new Date()), addDays(fmt(new Date()), 6)])
const loading = ref(false)

async function load() {
  if (!range.value) return
  loading.value = true
  try {
    const res = await reqTeacherSummary({
      start_date: range.value[0],
      end_date: range.value[1],
    })
    slots.value = res.data.slots
    rows.value = res.data.teachers
  } finally {
    loading.value = false
  }
}

const columns = computed<DataTableColumns<Row>>(() => {
  const base: DataTableColumns<Row> = [
    { title: "教师", key: "teacher_name", width: 100, fixed: "left" },
    { title: "学科", key: "subject_name", width: 80, fixed: "left" },
  ]
  for (const s of slots.value) {
    base.push({
      title: s.name,
      key: `slot-${s.id}`,
      width: 70,
      render: (row) => row.counts[String(s.id)] ?? 0,
    })
  }
  base.push({
    title: "合计(加权)",
    key: "total",
    width: 100,
    fixed: "right",
    render: (row) => row.total,
  })
  return base
})

onMounted(load)
</script>

<template>
  <div>
    <h3 class="page-title">教师课时汇总</h3>
    <div class="toolbar">
      <n-date-picker
        v-model:formatted-value="range"
        type="daterange"
        value-format="yyyy-MM-dd"
        @update:formatted-value="load"
      />
      <n-button @click="load">查询</n-button>
      <span style="color: #888">各时间段一列，合计 = Σ(次数 × 权重)</span>
    </div>
    <n-data-table
      :columns="columns"
      :data="rows"
      :loading="loading"
      :bordered="true"
      :scroll-x="1400"
      :single-line="false"
    />
  </div>
</template>
