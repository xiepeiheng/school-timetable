<script setup lang="ts">
import { onMounted, ref } from "vue"
import { useMessage } from "naive-ui"
import {
  reqExportMonthly,
  reqExportTeacherSheets,
  reqTemplateList,
} from "@/api/timetable"
import type { ScheduleTemplate } from "@/api/timetable/type"
import { fmt } from "@/utils/dates"

const message = useMessage()
const templates = ref<ScheduleTemplate[]>([])
const templateId = ref<number | null>(null)

const month = ref<string>(defaultMonth())
const exportingMonth = ref(false)

const range = ref<[string, string]>(currentMonthRange())
const exportingTeachers = ref(false)

function defaultMonth() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`
}

function currentMonthRange(): [string, string] {
  const now = new Date()
  const first = new Date(now.getFullYear(), now.getMonth(), 1)
  const last = new Date(now.getFullYear(), now.getMonth() + 1, 0)
  return [fmt(first), fmt(last)]
}

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

async function exportMonthly() {
  if (!month.value) return message.warning("请选择月份")
  if (!templateId.value) return message.warning("请选择模板")
  exportingMonth.value = true
  try {
    const blob = await reqExportMonthly({
      month: month.value,
      template: templateId.value,
    })
    const [year, mon] = month.value.split("-")
    download(blob, `${year}年${Number(mon)}月高一（1）部课时（分班后）.xlsx`)
    message.success("已导出")
  } finally {
    exportingMonth.value = false
  }
}

async function exportTeachers() {
  if (!range.value || !range.value[0] || !range.value[1])
    return message.warning("请选择起止日期")
  exportingTeachers.value = true
  try {
    const blob = await reqExportTeacherSheets({
      start: range.value[0],
      end: range.value[1],
    })
    download(blob, `教师个人课表_${range.value[0]}_${range.value[1]}.xlsx`)
    message.success("已导出")
  } finally {
    exportingTeachers.value = false
  }
}

onMounted(async () => {
  templates.value = (await reqTemplateList()).data.items
  if (templates.value.length) {
    const preferred =
      templates.value.find((t) => t.is_default) || templates.value[0]
    templateId.value = preferred.id
  }
})
</script>

<template>
  <div>
    <h3 class="page-title">导出</h3>

    <n-card title="月度课时（给核算用）" style="max-width: 640px; margin-bottom: 16px">
      <n-form>
        <n-form-item label="月份">
          <n-date-picker
            v-model:formatted-value="month"
            type="month"
            value-format="yyyy-MM"
            clearable
          />
        </n-form-item>
        <n-form-item label="详细课表模板">
          <n-select
            v-model:value="templateId"
            :options="templates.map((t) => ({ label: t.name, value: t.id }))"
          />
        </n-form-item>
        <n-alert type="info" :bordered="false">
          导出该月实际课时（周一至周五课/自习、周六日课/自习）+ 所选模板的详细课表 +
          监考（仅教师列）。日期只列有课的；合计列为公式。
        </n-alert>
      </n-form>
      <template #action>
        <n-button type="primary" :loading="exportingMonth" @click="exportMonthly">
          导出 Excel
        </n-button>
      </template>
    </n-card>

    <n-card title="教师个人课表（给老师自查用）" style="max-width: 640px">
      <n-form>
        <n-form-item label="起止日期">
          <n-date-picker
            v-model:formatted-value="range"
            type="daterange"
            value-format="yyyy-MM-dd"
            clearable
          />
        </n-form-item>
        <n-alert type="info" :bordered="false">
          每个老师一个页签（学科-老师），行=区间内每一天（没课也显示），列=节次+合计，
          格子=班级名；换课/代课/异常会上色，并在下方列出标注与备注。
        </n-alert>
      </n-form>
      <template #action>
        <n-button type="primary" :loading="exportingTeachers" @click="exportTeachers">
          导出 Excel
        </n-button>
      </template>
    </n-card>
  </div>
</template>
