<script setup lang="ts">
import { h, onMounted, ref } from "vue"
import { NButton, NSpace, useMessage, type DataTableColumns } from "naive-ui"
import {
  reqClassCreate,
  reqClassDelete,
  reqClassList,
  reqClassUpdate,
  reqTeacherList,
} from "@/api/base"
import type { SchoolClass, Teacher } from "@/api/base/type"

const message = useMessage()
const rows = ref<SchoolClass[]>([])
const teachers = ref<Teacher[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const size = ref(20)
const showModal = ref(false)
const editing = ref<SchoolClass | null>(null)
const form = ref<Partial<SchoolClass>>({
  name: "",
  grade: "高一1部",
  homeroom_teacher: null,
  sort_order: 0,
  is_active: true,
})

const teacherOptions = () =>
  teachers.value.map((t) => ({ label: t.name, value: t.id }))

async function load() {
  loading.value = true
  try {
    const res = await reqClassList({ page: page.value, size: size.value })
    rows.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.value = {
    name: "",
    grade: "高一1部",
    homeroom_teacher: null,
    sort_order: rows.value.length,
    is_active: true,
  }
  showModal.value = true
}

function openEdit(row: SchoolClass) {
  editing.value = row
  form.value = { ...row }
  showModal.value = true
}

async function save() {
  if (!form.value.name) return message.warning("请填写班级名称")
  if (editing.value) {
    await reqClassUpdate(editing.value.id, form.value)
  } else {
    await reqClassCreate(form.value)
  }
  message.success("已保存")
  showModal.value = false
  load()
}

async function remove(row: SchoolClass) {
  await reqClassDelete(row.id)
  message.success("已停用")
  load()
}

const columns: DataTableColumns<SchoolClass> = [
  { title: "班级", key: "name" },
  { title: "部/年级", key: "grade" },
  { title: "班主任", key: "homeroom_teacher_name", render: (r) => r.homeroom_teacher_name || "-" },
  { title: "排序", key: "sort_order", width: 80 },
  { title: "启用", key: "is_active", width: 80, render: (r) => (r.is_active ? "是" : "否") },
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

onMounted(async () => {
  teachers.value = (await reqTeacherList({ size: 500 })).data.items
  load()
})
</script>

<template>
  <div>
    <h3 class="page-title">班级</h3>
    <div class="toolbar">
      <n-button type="primary" @click="openCreate">新增班级</n-button>
      <n-button @click="load">刷新</n-button>
    </div>
    <n-data-table
      :columns="columns"
      :data="rows"
      :loading="loading"
      :bordered="true"
      remote
      :pagination="{
        page: page,
        pageSize: size,
        itemCount: total,
        'onUpdate:page': (p: number) => { page = p; load() },
      }"
    />

    <n-modal v-model:show="showModal">
      <n-card style="width: 420px" :title="editing ? '编辑班级' : '新增班级'">
        <n-form>
          <n-form-item label="班级名称">
            <n-input v-model:value="form.name" />
          </n-form-item>
          <n-form-item label="部/年级">
            <n-input v-model:value="form.grade" />
          </n-form-item>
          <n-form-item label="班主任">
            <n-select
              v-model:value="form.homeroom_teacher"
              :options="teacherOptions()"
              clearable
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
