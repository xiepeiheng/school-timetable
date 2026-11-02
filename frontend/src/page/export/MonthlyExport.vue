<script setup lang="ts">
import { ref } from "vue"
import { useMessage } from "naive-ui"
import { reqExportMonthly, reqExportTeacherSheets } from "@/api/timetable"
import { fmt } from "@/utils/dates"

const message = useMessage()

const range = ref<[string, string]>(currentMonthRange())
const exportingMonth = ref(false)

const teacherRange = ref<[string, string]>(currentMonthRange())
const exportingTeachers = ref(false)

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
  if (!range.value || !range.value[0] || !range.value[1])
    return message.warning("请选择起止日期")
  exportingMonth.value = true
  try {
    const blob = await reqExportMonthly({
      start: range.value[0],
      end: range.value[1],
    })
    download(
      blob,
      `高一（1）部课时_${range.value[0]}_${range.value[1]}.xlsx`,
    )
    message.success("已导出")
  } finally {
    exportingMonth.value = false
  }
}

async function exportTeachers() {
  if (!teacherRange.value || !teacherRange.value[0] || !teacherRange.value[1])
    return message.warning("请选择起止日期")
  exportingTeachers.value = true
  try {
    const blob = await reqExportTeacherSheets({
      start: teacherRange.value[0],
      end: teacherRange.value[1],
    })
    download(
      blob,
      `教师个人课表_${teacherRange.value[0]}_${teacherRange.value[1]}.xlsx`,
    )
    message.success("已导出")
  } finally {
    exportingTeachers.value = false
  }
}
</script>

<template>
  <div>
    <h3 class="page-title">导出</h3>

    <n-card title="课时核算（给核算用）" style="max-width: 640px; margin-bottom: 16px">
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
          导出该区间的实际课时（周一至周五课/自习、周六日课/自习）+
          课时汇总。日期只列有课的；空表保留；系数合计按记录写入时的权重计算。
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
            v-model:formatted-value="teacherRange"
            type="daterange"
            value-format="yyyy-MM-dd"
            clearable
          />
        </n-form-item>
        <n-alert type="info" :bordered="false">
          每个老师一个页签（学科-老师），行=区间内每一天（没课也显示），列=节次+合计+按系数合计，
          表尾两行为各节次合计与按系数合计；格子=班级名；换课/代课/异常会上色，并在下方列出标注与备注。
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
