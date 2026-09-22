<script setup lang="ts">
import { h, onMounted, ref } from "vue"
import { NButton, NSpace, useMessage, type DataTableColumns } from "naive-ui"
import {
  reqSubjectCreate,
  reqSubjectDelete,
  reqSubjectList,
  reqSubjectUpdate,
} from "@/api/base"
import type { Subject } from "@/api/base/type"

const message = useMessage()
const rows = ref<Subject[]>([])
const loading = ref(false)
const showModal = ref(false)
const editing = ref<Subject | null>(null)
const form = ref<Partial<Subject>>({ name: "", color: "", sort_order: 0, is_active: true })

async function load() {
  loading.value = true
  try {
    rows.value = (await reqSubjectList()).data
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.value = { name: "", color: "", sort_order: rows.value.length, is_active: true }
  showModal.value = true
}

function openEdit(row: Subject) {
  editing.value = row
  form.value = { ...row }
  showModal.value = true
}

async function save() {
  if (!form.value.name) return message.warning("请填写名称")
  if (editing.value) {
    await reqSubjectUpdate(editing.value.id, form.value)
  } else {
    await reqSubjectCreate(form.value)
  }
  message.success("已保存")
  showModal.value = false
  load()
}

async function remove(row: Subject) {
  await reqSubjectDelete(row.id)
  message.success("已停用/删除")
  load()
}

const columns: DataTableColumns<Subject> = [
  { title: "名称", key: "name" },
  { title: "颜色", key: "color", render: (r) => r.color || "-" },
  { title: "排序", key: "sort_order", width: 80 },
  {
    title: "启用",
    key: "is_active",
    width: 80,
    render: (r) => (r.is_active ? "是" : "否"),
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
    <h3 class="page-title">学科</h3>
    <div class="toolbar">
      <n-button type="primary" @click="openCreate">新增学科</n-button>
      <n-button @click="load">刷新</n-button>
    </div>
    <n-data-table :columns="columns" :data="rows" :loading="loading" :bordered="true" />

    <n-modal v-model:show="showModal">
      <n-card style="width: 420px" :title="editing ? '编辑学科' : '新增学科'">
        <n-form>
          <n-form-item label="名称">
            <n-input v-model:value="form.name" />
          </n-form-item>
          <n-form-item label="颜色">
            <n-input v-model:value="form.color" placeholder="#RRGGBB（可选）" />
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
