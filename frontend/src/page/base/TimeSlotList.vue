<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue"
import { NButton, NSpace, useMessage, type DataTableColumns } from "naive-ui"
import {
  reqReportGroupList,
  reqReportGroupUpdate,
  reqTimeSlotCreate,
  reqTimeSlotDelete,
  reqTimeSlotList,
  reqTimeSlotReorder,
  reqTimeSlotUpdate,
} from "@/api/base"
import type { ReportGroup, TimeSlot } from "@/api/base/type"

const message = useMessage()
const rows = ref<TimeSlot[]>([])
const groups = ref<ReportGroup[]>([])
const groupCoefficients = ref<Record<number, number>>({})
const loading = ref(false)
const showModal = ref(false)
const editing = ref<TimeSlot | null>(null)
const form = ref<Partial<TimeSlot>>({
  name: "",
  sort_order: 0,
  report_group: null,
  is_active: true,
})

const groupOptions = computed(() =>
  groups.value.map((g) => ({
    label: `${g.kind_display}（${g.coefficient}）`,
    value: g.id,
  })),
)

async function load() {
  loading.value = true
  try {
    const [slots, gs] = await Promise.all([reqTimeSlotList(), reqReportGroupList()])
    rows.value = slots.data
    groups.value = gs.data
    groupCoefficients.value = Object.fromEntries(
      gs.data.map((g) => [g.id, Number(g.coefficient)]),
    )
  } finally {
    loading.value = false
  }
}

async function saveGroupCoefficients() {
  await Promise.all(
    groups.value.map((g) =>
      reqReportGroupUpdate(g.id, {
        coefficient: String(groupCoefficients.value[g.id] ?? 0),
      }),
    ),
  )
  message.success("报告分组系数已保存")
  load()
}

function openCreate() {
  editing.value = null
  form.value = {
    name: "",
    sort_order: rows.value.length,
    report_group: null,
    is_active: true,
  }
  showModal.value = true
}

function openEdit(row: TimeSlot) {
  editing.value = row
  form.value = { ...row }
  showModal.value = true
}

async function save() {
  if (!form.value.name) return message.warning("请填写名称")
  if (editing.value) {
    await reqTimeSlotUpdate(editing.value.id, form.value)
  } else {
    await reqTimeSlotCreate(form.value)
  }
  message.success("已保存")
  showModal.value = false
  load()
}

async function remove(row: TimeSlot) {
  await reqTimeSlotDelete(row.id)
  message.success("已停用")
  load()
}

async function move(index: number, delta: number) {
  const target = index + delta
  if (target < 0 || target >= rows.value.length) return
  const list = rows.value.slice()
  const [item] = list.splice(index, 1)
  list.splice(target, 0, item)
  await reqTimeSlotReorder(list.map((s) => s.id))
  load()
}

const columns: DataTableColumns<TimeSlot> = [
  { title: "名称", key: "name" },
  { title: "报告分组", key: "report_group_name", width: 120, render: (r) => r.report_group_name || "—" },
  { title: "排序", key: "sort_order", width: 80 },
  { title: "启用", key: "is_active", width: 80, render: (r) => (r.is_active ? "是" : "否") },
  {
    title: "排序调整",
    key: "move",
    width: 120,
    render: (_row, index) =>
      h(NSpace, null, {
        default: () => [
          h(NButton, { size: "tiny", onClick: () => move(index, -1) }, { default: () => "↑" }),
          h(NButton, { size: "tiny", onClick: () => move(index, 1) }, { default: () => "↓" }),
        ],
      }),
  },
  {
    title: "操作",
    key: "actions",
    width: 160,
    render: (row) =>
      h(NSpace, null, {
        default: () => [
          h(NButton, { size: "small", onClick: () => openEdit(row) }, { default: () => "编辑" }),
          h(
            NButton,
            { size: "small", type: "error", ghost: true, onClick: () => remove(row) },
            { default: () => "停用" },
          ),
        ],
      }),
  },
]

onMounted(load)
</script>

<template>
  <div>
    <h3 class="page-title">时间段</h3>
    <div class="toolbar">
      <n-button type="primary" @click="openCreate">新增时间段</n-button>
      <n-button @click="load">刷新</n-button>
    </div>

    <n-card size="small" title="报告分组系数" style="margin-bottom: 12px">
      <n-space align="center">
        <div
          v-for="g in groups"
          :key="g.id"
          style="display: flex; align-items: center; gap: 8px"
        >
          <span>{{ g.kind_display }}</span>
          <n-input-number
            v-model:value="groupCoefficients[g.id]"
            :min="0"
            :step="0.1"
            :precision="2"
            style="width: 110px"
          />
        </div>
        <n-button type="primary" secondary @click="saveGroupCoefficients">
          保存系数
        </n-button>
      </n-space>
    </n-card>

    <n-data-table :columns="columns" :data="rows" :loading="loading" :bordered="true" />

    <n-modal v-model:show="showModal">
      <n-card style="width: 420px" :title="editing ? '编辑时间段' : '新增时间段'">
        <n-form>
          <n-form-item label="名称">
            <n-input v-model:value="form.name" placeholder="如：早读 / 一 / 晚一" />
          </n-form-item>
          <n-form-item label="报告分组">
            <n-select
              v-model:value="form.report_group"
              :options="groupOptions"
              clearable
              placeholder="正课 / 自习"
            />
          </n-form-item>
          <n-form-item label="排序">
            <n-input-number v-model:value="form.sort_order" :min="0" />
          </n-form-item>
          <n-form-item label="启用">
            <n-switch v-model:value="form.is_active" />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="showModal = false">取消</n-button>
            <n-button type="primary" @click="save">保存</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>
  </div>
</template>
