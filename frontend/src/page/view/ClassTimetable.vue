<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { reqClassList, reqSubjectList } from "@/api/base"
import type { SchoolClass, Subject } from "@/api/base/type"
import { reqClassTimetable } from "@/api/timetable"
import type { SlotInfo } from "@/api/timetable/type"
import { addDays, fmt } from "@/utils/dates"

const classes = ref<SchoolClass[]>([])
const subjects = ref<Subject[]>([])
const slots = ref<SlotInfo[]>([])
const sessions = ref<Record<string, { subject_name: string; teacher_name: string }>>({})
const selectedClass = ref<number | null>(null)
const range = ref<[string, string]>([fmt(new Date()), addDays(fmt(new Date()), 6)])
const loading = ref(false)

const subjectMap = computed(() =>
  Object.fromEntries(subjects.value.map((s) => [s.id, s])),
)

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
  if (!selectedClass.value || !range.value) return
  loading.value = true
  try {
    const res = await reqClassTimetable({
      school_class: selectedClass.value,
      start_date: range.value[0],
      end_date: range.value[1],
    })
    slots.value = res.data.slots
    const map: Record<string, { subject_name: string; teacher_name: string }> = {}
    for (const s of res.data.sessions) {
      map[`${s.date}-${s.time_slot}`] = s
    }
    sessions.value = map
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
  const [cls, sub] = await Promise.all([reqClassList({ size: 500 }), reqSubjectList()])
  classes.value = cls.data.items
  subjects.value = sub.data
  if (classes.value.length) {
    selectedClass.value = classes.value[0].id
    await load()
  }
})
</script>

<template>
  <div>
    <h3 class="page-title">班级课表</h3>
    <div class="toolbar">
      <n-select
        v-model:value="selectedClass"
        :options="classes.map((c) => ({ label: c.name, value: c.id }))"
        style="width: 140px"
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
              <td v-for="d in dates" :key="d + slot.id" class="cell">
                <template v-if="cell(d, slot.id)">
                  <div
                    class="subject"
                    :style="{
                      color: subjectMap[cell(d, slot.id)!.subject_name]?.color || undefined,
                    }"
                  >
                    {{ cell(d, slot.id)!.subject_name }}
                  </div>
                  <small>{{ cell(d, slot.id)!.teacher_name || "" }}</small>
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
small {
  color: #888;
}
</style>
