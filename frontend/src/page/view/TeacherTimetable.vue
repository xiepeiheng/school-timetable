<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { reqTeacherList } from "@/api/base"
import type { Teacher } from "@/api/base/type"
import { reqTeacherTimetable } from "@/api/timetable"
import type { SlotInfo } from "@/api/timetable/type"
import { addDays, fmt } from "@/utils/dates"

const teachers = ref<Teacher[]>([])
const slots = ref<SlotInfo[]>([])
const sessions = ref<
  Record<string, { school_class_name: string; subject_name: string }>
>({})
const conflicts = ref<
  { date: string; time_slot: number; items: { school_class_name: string }[] }[]
>([])
const selectedTeacher = ref<number | null>(null)
const range = ref<[string, string]>([fmt(new Date()), addDays(fmt(new Date()), 6)])
const loading = ref(false)

const dates = computed(() => {
  const [start, end] = range.value
  const list: string[] = []
  let cur = start
  while (cur <= end && list.length < 62) {
    list.push(cur)
    cur = addDays(cur, 1)
  }
  return list
})

const tableMinWidth = computed(() =>
  dates.value.length > 7 ? `${dates.value.length * 70 + 70}px` : "0",
)

async function load() {
  if (!selectedTeacher.value || !range.value) return
  loading.value = true
  try {
    const res = await reqTeacherTimetable({
      teacher: selectedTeacher.value,
      start_date: range.value[0],
      end_date: range.value[1],
    })
    slots.value = res.data.slots
    const map: Record<string, { school_class_name: string; subject_name: string }> = {}
    for (const s of res.data.sessions) {
      const key = `${s.date}-${s.time_slot}`
      if (map[key]) {
        map[key].school_class_name += `/${s.school_class_name}`
      } else {
        map[key] = { school_class_name: s.school_class_name, subject_name: s.subject_name }
      }
    }
    sessions.value = map
    conflicts.value = res.data.conflicts
  } finally {
    loading.value = false
  }
}

function cell(date: string, slotId: number) {
  return sessions.value[`${date}-${slotId}`]
}

function weekdayLabel(date: string) {
  return ["一", "二", "三", "四", "五", "六", "日"][(new Date(date).getDay() + 6) % 7]
}

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
    <h3 class="page-title">教师课表</h3>
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
    </div>

    <n-alert v-if="conflicts.length" type="warning" style="margin-bottom: 12px">
      检测到 {{ conflicts.length }} 处时间冲突：
      <span v-for="c in conflicts" :key="c.date + c.time_slot">
        {{ c.date }}（{{ c.items.map((i) => i.school_class_name).join("、") }}）
      </span>
    </n-alert>

    <n-spin :show="loading">
      <div style="overflow: auto">
        <table class="tt-grid" :style="{ minWidth: tableMinWidth }">
          <thead>
            <tr>
              <th class="slot-col">时间段</th>
              <th v-for="d in dates" :key="d">
                周{{ weekdayLabel(d) }}<br /><small>{{ d.slice(5) }}</small>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="slot in slots" :key="slot.id">
              <td class="slot-col">{{ slot.name }}</td>
              <td
                v-for="d in dates"
                :key="d + slot.id"
                class="cell"
                :class="{ conflict: conflicts.some((c) => c.date === d && c.time_slot === slot.id) }"
              >
                <template v-if="cell(d, slot.id)">
                  <div class="subject">{{ cell(d, slot.id)!.subject_name }}</div>
                  <small>{{ cell(d, slot.id)!.school_class_name }}</small>
                </template>
                <span v-else class="empty">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </n-spin>
  </div>
</template>

<style scoped>
.tt-grid {
  border-collapse: collapse;
  width: 100%;
  table-layout: fixed;
  background: #fff;
}
.tt-grid th,
.tt-grid td {
  border: 1px solid #e0e0e6;
  padding: 4px 2px;
  text-align: center;
  font-size: 13px;
  overflow: hidden;
  word-break: break-all;
}
.tt-grid th {
  background: #fafafc;
}
.slot-col {
  width: 64px;
  background: #fafafc;
  font-weight: 600;
}
.subject {
  font-weight: 600;
}
.empty {
  color: #ccc;
}
.cell.conflict {
  background: #fff3e0;
}
small {
  color: #888;
}
</style>
