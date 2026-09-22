<script setup lang="ts">
import { h, onMounted, ref } from "vue"
import { NButton, NSpace, useMessage, type DataTableColumns } from "naive-ui"
import {
  reqSubjectList,
  reqTeacherCreate,
  reqTeacherDelete,
  reqTeacherList,
  reqTeacherUpdate,
} from "@/api/base"
import type { Subject, Teacher } from "@/api/base/type"

const message = useMessage()
const rows = ref<Teacher[]>([])
const subjects = ref<Subject[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const size = ref(20)
const showModal = ref(false)
const editing = ref<Teacher | null>(null)
const form = ref<Partial<Teacher>>({
  name: "",
  subject: undefined,
  note: "",
  is_active: true,
})

const subjectOptions = () =>
  subjects.value.map((s) => ({ label: s.name, value: s.id }))

async function load() {
  loading.value = true
  try {
    const res = await reqTeacherList({ page: page.value, size: size.value })
    rows.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.value = { name: "", subject: subjects.value[0]?.id, note: "", is_active: true }
  showModal.value = true
}

function openEdit(row: Teacher) {
  editing.value = row
  form.value = { ...row }
  showModal.value = true
}

async function save() {
  if (!form.value.name || !form.value.subject) return message.warning("请填写姓名并选择学科")
  if (editing.value) {
    await reqTeacherUpdate(editing.value.id, form.value)
  } else {
    await reqTeacherCreate(form.value)
  }
  message.success("已保存")
  showModal.value = false
  load()
}

async function remove(row: Teacher) {
  await reqTeacherDelete(row.id)
  message.success("已停用")
  load()
}

const columns: DataTableColumns<Teacher> = [
  { title: "姓名", key: "name" },
  { title: "学科", key: "subject_name" },
  { title: "备注", key: "note", render: (r) => r.note || "-" },
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
  subjects.value = (await reqSubjectList()).data
  load()
})
</script>

<template>
  <div>
    <h3 class="page-title">教师</h3>
    <div class="toolbar">
      <n-button type="primary" @click="openCreate">新增教师</n-button>
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
        showSizePicker: true,
        pageSizes: [10, 20, 50],
        'onUpdate:page': (p: number) => { page = p; load() },
        'onUpdate:pageSize': (s: number) => { size = s; page = 1; load() },
      }"
    />

    <n-modal v-model:show="showModal">
      <n-card style="width: 420px" :title="editing ? '编辑教师' : '新增教师'">
        <n-form>
          <n-form-item label="姓名">
            <n-input v-model:value="form.name" />
          </n-form-item>
          <n-form-item label="学科">
            <n-select v-model:value="form.subject" :options="subjectOptions()" />
          </n-form-item>
          <n-form-item label="备注">
            <n-input v-model:value="form.note" />
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
