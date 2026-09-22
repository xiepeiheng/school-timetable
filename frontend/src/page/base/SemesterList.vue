<script setup lang="ts">
import { h, onMounted, ref } from "vue"
import { NButton, NSpace, useMessage, type DataTableColumns } from "naive-ui"
import {
  reqSemesterCreate,
  reqSemesterDelete,
  reqSemesterList,
  reqSemesterUpdate,
} from "@/api/base"
import type { Semester } from "@/api/base/type"

const message = useMessage()
const rows = ref<Semester[]>([])
const loading = ref(false)
const showModal = ref(false)
const editing = ref<Semester | null>(null)
const form = ref<Partial<Semester>>({ name: "", start_date: null, end_date: null })

async function load() {
  loading.value = true
  try {
    rows.value = (await reqSemesterList()).data
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.value = { name: "", start_date: null, end_date: null }
  showModal.value = true
}

function openEdit(row: Semester) {
  editing.value = row
  form.value = { ...row }
  showModal.value = true
}

async function save() {
  if (!form.value.name) return message.warning("请填写名称")
  if (editing.value) {
    await reqSemesterUpdate(editing.value.id, form.value)
  } else {
    await reqSemesterCreate(form.value)
  }
  message.success("已保存")
  showModal.value = false
  load()
}

async function remove(row: Semester) {
  await reqSemesterDelete(row.id)
  message.success("已删除")
  load()
}

const columns: DataTableColumns<Semester> = [
  { title: "名称", key: "name" },
  { title: "开始", key: "start_date", render: (r) => r.start_date || "-" },
  { title: "结束", key: "end_date", render: (r) => r.end_date || "-" },
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
            { default: () => "删除" },
          ),
        ],
      }),
  },
]

onMounted(load)
</script>

<template>
  <div>
    <h3 class="page-title">学期</h3>
    <div class="toolbar">
      <n-button type="primary" @click="openCreate">新增学期</n-button>
      <n-button @click="load">刷新</n-button>
    </div>
    <n-data-table :columns="columns" :data="rows" :loading="loading" :bordered="true" />

    <n-modal v-model:show="showModal">
      <n-card style="width: 420px" :title="editing ? '编辑学期' : '新增学期'">
        <n-form>
          <n-form-item label="名称">
            <n-input v-model:value="form.name" />
          </n-form-item>
          <n-form-item label="开始日期">
            <n-date-picker v-model:formatted-value="form.start_date" value-format="yyyy-MM-dd" />
          </n-form-item>
          <n-form-item label="结束日期">
            <n-date-picker v-model:formatted-value="form.end_date" value-format="yyyy-MM-dd" />
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
