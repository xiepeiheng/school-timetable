<script setup lang="ts">
import { ref } from "vue"
import { useMessage } from "naive-ui"
import { reqExportTeacherSheets } from "@/api/timetable"
import { fmt } from "@/utils/dates"

const message = useMessage()

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

    <n-card title="教师个人课表" style="max-width: 640px">
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
          第一个页签为教师绩效汇总；每个老师一个页签（学科-老师），包含每日课表、任课统计和绩效系数计算；
          最后为每个启用班级的课表。系数可在导出后的表格中修改，公式会自动重算。
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
