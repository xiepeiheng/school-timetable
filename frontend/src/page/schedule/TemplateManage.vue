<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue"
import {
  NButton,
  NSpace,
  useDialog,
  useMessage,
  type DataTableColumns,
} from "naive-ui"
import { reqClassList, reqSubjectList, reqTimeSlotList } from "@/api/base"
import type { SchoolClass, Subject, TimeSlot } from "@/api/base/type"
import {
  reqTemplateApply,
  reqTemplateCreate,
  reqTemplateCreateFromWeek,
  reqTemplateDelete,
  reqTemplateDuplicate,
  reqTemplateEntryBulk,
  reqTemplateEntryList,
  reqTemplateList,
  reqTemplateUpdate,
} from "@/api/timetable"
import type { ScheduleTemplate, TemplateEntry } from "@/api/timetable/type"
import WeekGrid, {
  type GridCell,
  type GridColumn,
} from "@/components/WeekGrid.vue"
import SubjectPicker from "@/components/SubjectPicker.vue"
import { addDays, WEEKDAY_NAMES } from "@/utils/dates"

const message = useMessage()
const dialog = useDialog()

const templates = ref<ScheduleTemplate[]>([])
const classes = ref<SchoolClass[]>([])
const subjects = ref<Subject[]>([])
const slots = ref<TimeSlot[]>([])
const loading = ref(false)

const selectedTemplateId = ref<number | null>(null)
const selectedClass = ref<number | null>(null)
const entries = ref<Record<string, TemplateEntry>>({})

const activeSlots = computed(() => slots.value.filter((s) => s.is_active))
const subjectMap = computed(() =>
  Object.fromEntries(subjects.value.map((s) => [s.id, s])),
)
const selectedTemplate = computed(() =>
  templates.value.find((t) => t.id === selectedTemplateId.value),
)

const gridColumns: GridColumn[] = WEEKDAY_NAMES.map((label, i) => ({
  key: String(i + 1),
  label,
}))

const classOptions = computed(() =>
  classes.value.map((c) => ({ label: c.name, value: c.id })),
)
const subjectOptions = computed(() =>
  subjects.value.map((s) => ({ label: s.name, value: s.id })),
)

// ── 数据 ──
async function loadTemplates() {
  templates.value = (await reqTemplateList()).data.items
  if (
    selectedTemplateId.value &&
    !templates.value.some((t) => t.id === selectedTemplateId.value)
  ) {
    selectedTemplateId.value = null
    entries.value = {}
  }
}

async function loadEntries() {
  if (!selectedTemplateId.value || !selectedClass.value) {
    entries.value = {}
    return
  }
  loading.value = true
  try {
    const res = await reqTemplateEntryList({
      template: selectedTemplateId.value,
      school_class: selectedClass.value,
    })
    const map: Record<string, TemplateEntry> = {}
    for (const e of res.data.items) {
      map[`${e.weekday}-${e.time_slot}`] = e
    }
    entries.value = map
  } finally {
    loading.value = false
  }
}

function entryOf(weekdayKey: string, slotId: number) {
  return entries.value[`${weekdayKey}-${slotId}`]
}

function gridCell(weekdayKey: string, slotId: number): GridCell | undefined {
  const e = entryOf(weekdayKey, slotId)
  if (!e) return undefined
  return { main: e.subject_name, color: subjectMap.value[e.subject]?.color }
}

// ── 单元格编辑 ──
const cellModal = ref(false)
const cellForm = ref<{
  weekday: number
  slotId: number
  slotName: string
  subject: number | null
}>({ weekday: 1, slotId: 0, slotName: "", subject: null })

function openCell(weekdayKey: string, slot: { id: number; name: string }) {
  const weekday = Number(weekdayKey)
  const e = entryOf(weekdayKey, slot.id)
  cellForm.value = {
    weekday,
    slotId: slot.id,
    slotName: slot.name,
    subject: e?.subject ?? null,
  }
  cellModal.value = true
}

async function saveCell() {
  if (!selectedTemplateId.value || !selectedClass.value) return
  await reqTemplateEntryBulk([
    {
      template: selectedTemplateId.value,
      school_class: selectedClass.value,
      weekday: cellForm.value.weekday,
      time_slot: cellForm.value.slotId,
      subject: cellForm.value.subject,
    },
  ])
  cellModal.value = false
  await loadEntries()
}

async function clearCell() {
  cellForm.value.subject = null
  await saveCell()
}

// ── 工具：清空本班 ──
async function clearClass() {
  if (!selectedTemplateId.value || !selectedClass.value) return
  const items = Object.values(entries.value).map((e) => ({
    template: e.template,
    school_class: e.school_class,
    weekday: e.weekday,
    time_slot: e.time_slot,
    subject: null,
  }))
  if (!items.length) return message.info("本班没有可清空的内容")
  await reqTemplateEntryBulk(items)
  message.success("已清空本班")
  await loadEntries()
}

// ── 工具：复制周X到周Y ──
const copyModal = ref(false)
const copyForm = ref({ source: 1, target: 2 })
async function doCopyWeekday() {
  if (!selectedTemplateId.value || !selectedClass.value) return
  if (copyForm.value.source === copyForm.value.target)
    return message.warning("源和目标不能相同")
  const src = String(copyForm.value.source)
  const dst = String(copyForm.value.target)
  const items: {
    template: number
    school_class: number
    weekday: number
    time_slot: number
    subject: number | null
  }[] = []
  const slotIds = new Set<number>()
  for (const slot of activeSlots.value) {
    const s = entryOf(src, slot.id)
    const d = entryOf(dst, slot.id)
    if (s || d) slotIds.add(slot.id)
  }
  for (const slotId of slotIds) {
    const s = entryOf(src, slotId)
    items.push({
      template: selectedTemplateId.value,
      school_class: selectedClass.value,
      weekday: copyForm.value.target,
      time_slot: slotId,
      subject: s ? s.subject : null,
    })
  }
  await reqTemplateEntryBulk(items)
  message.success("已复制")
  copyModal.value = false
  await loadEntries()
}

// ── 新建空白模板 ──
const createModal = ref(false)
const createForm = ref({ name: "", note: "", is_default: false })
async function doCreate() {
  if (!createForm.value.name) return message.warning("请填写模板名称")
  const res = await reqTemplateCreate(createForm.value)
  message.success("已创建")
  createModal.value = false
  createForm.value = { name: "", note: "", is_default: false }
  await loadTemplates()
  selectedTemplateId.value = res.data.id
  await loadEntries()
}

// ── 从某周生成模板 ──
const fromWeekModal = ref(false)
const fromWeekForm = ref({
  name: "",
  note: "",
  is_default: false,
  monday: "",
})
function isDateDisabled(timestamp: number) {
  return new Date(timestamp).getDay() !== 1
}
async function doCreateFromWeek() {
  if (!fromWeekForm.value.name || !fromWeekForm.value.monday)
    return message.warning("请填写名称并选择周一")
  const res = await reqTemplateCreateFromWeek({
    name: fromWeekForm.value.name,
    note: fromWeekForm.value.note,
    is_default: fromWeekForm.value.is_default,
    start_date: fromWeekForm.value.monday,
    end_date: addDays(fromWeekForm.value.monday, 6),
  })
  message.success("模板已保存")
  fromWeekModal.value = false
  fromWeekForm.value = { name: "", note: "", is_default: false, monday: "" }
  await loadTemplates()
  selectedTemplateId.value = res.data.id
  await loadEntries()
}

// ── 模板信息 ──
const infoModal = ref(false)
const infoForm = ref({ name: "", note: "", is_default: false })
function openInfo(t: ScheduleTemplate) {
  selectedTemplateId.value = t.id
  infoForm.value = { name: t.name, note: t.note, is_default: t.is_default }
  infoModal.value = true
}
async function saveInfo() {
  if (!selectedTemplateId.value) return
  await reqTemplateUpdate(selectedTemplateId.value, infoForm.value)
  message.success("已保存")
  infoModal.value = false
  await loadTemplates()
  await loadEntries()
}

async function setDefault(t: ScheduleTemplate) {
  await reqTemplateUpdate(t.id, { is_default: true })
  message.success("已设为默认")
  await loadTemplates()
}

async function duplicate(t: ScheduleTemplate) {
  const res = await reqTemplateDuplicate(t.id)
  message.success("已复制")
  await loadTemplates()
  selectedTemplateId.value = res.data.id
  await loadEntries()
}

function remove(t: ScheduleTemplate) {
  dialog.warning({
    title: "删除模板",
    content: `确定删除模板「${t.name}」及其全部条目吗？`,
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      await reqTemplateDelete(t.id)
      message.success("已删除")
      await loadTemplates()
    },
  })
}

// ── 应用模板 ──
const applyModal = ref(false)
const applyForm = ref({ monday: "", overwrite: true })
async function doApply() {
  if (!selectedTemplateId.value || !applyForm.value.monday)
    return message.warning("请选择要排课的周一")
  const tpl = selectedTemplate.value
  const uncovered =
    tpl && applyForm.value.overwrite
      ? classes.value.length - tpl.class_count
      : 0
  if (uncovered > 0) {
    dialog.warning({
      title: "覆盖确认",
      content: `该模板只包含 ${tpl!.class_count} 个班级，覆盖应用会清空其余 ${uncovered} 个班级当周的课表，是否继续？`,
      positiveText: "继续",
      negativeText: "取消",
      onPositiveClick: () => applyNow(),
    })
  } else {
    await applyNow()
  }
}
async function applyNow() {
  const res = await reqTemplateApply({
    template: selectedTemplateId.value!,
    start_date: applyForm.value.monday,
    end_date: addDays(applyForm.value.monday, 6),
    overwrite: applyForm.value.overwrite,
  })
  message.success(`排课完成：新增 ${res.data.created}，跳过 ${res.data.skipped}`)
  applyModal.value = false
}

const columns: DataTableColumns<ScheduleTemplate> = [
  {
    title: "名称",
    key: "name",
    render: (t) =>
      h(
        "span",
        { style: t.id === selectedTemplateId.value ? "font-weight:700;color:#2080f0" : "" },
        t.name,
      ),
  },
  { title: "备注", key: "note" },
  { title: "条目数", key: "entry_count", width: 90 },
  { title: "覆盖班级", key: "class_count", width: 90 },
  {
    title: "默认",
    key: "is_default",
    width: 70,
    render: (t) => (t.is_default ? "是" : ""),
  },
  {
    title: "操作",
    key: "actions",
    width: 330,
    render: (row) =>
      h(NSpace, null, {
        default: () => [
          h(
            NButton,
            {
              size: "small",
              type: "primary",
              onClick: async () => {
                selectedTemplateId.value = row.id
                await loadEntries()
              },
            },
            { default: () => "编辑内容" },
          ),
          h(NButton, { size: "small", onClick: () => openInfo(row) }, { default: () => "信息" }),
          h(NButton, { size: "small", onClick: () => duplicate(row) }, { default: () => "复制" }),
          h(
            NButton,
            { size: "small", disabled: row.is_default, onClick: () => setDefault(row) },
            { default: () => "设为默认" },
          ),
          h(
            NButton,
            { size: "small", type: "error", ghost: true, onClick: () => remove(row) },
            { default: () => "删除" },
          ),
        ],
      }),
  },
]

onMounted(async () => {
  const [cls, sub, sl] = await Promise.all([
    reqClassList({ size: 500 }),
    reqSubjectList(),
    reqTimeSlotList(),
  ])
  classes.value = cls.data.items
  subjects.value = sub.data
  slots.value = sl.data
  if (classes.value.length) selectedClass.value = classes.value[0].id
  await loadTemplates()
})
</script>

<template>
  <div>
    <h3 class="page-title">模板管理</h3>
    <div class="toolbar">
      <n-button type="primary" @click="createModal = true">新建空白模板</n-button>
      <n-button @click="fromWeekModal = true">从某周生成模板</n-button>
      <n-button @click="loadTemplates">刷新</n-button>
    </div>
    <n-data-table :columns="columns" :data="templates" :bordered="true" />

    <n-divider />

    <div v-if="selectedTemplate" class="toolbar">
      <b>正在编辑：{{ selectedTemplate.name }}</b>
      <span style="margin-left: 12px">班级：</span>
      <n-select
        v-model:value="selectedClass"
        :options="classOptions"
        style="width: 140px"
        @update:value="loadEntries"
      />
      <n-button @click="clearClass">清空本班</n-button>
      <n-button @click="copyModal = true">复制周X到周Y</n-button>
      <n-button type="primary" @click="applyModal = true">应用该模板到某周</n-button>
    </div>
    <n-empty v-else description="请选择上方模板的「编辑内容」" />

    <n-spin v-if="selectedTemplate" :show="loading">
      <WeekGrid
        :slots="activeSlots"
        :columns="gridColumns"
        :cell="gridCell"
        @cell-click="openCell"
      />
      <n-alert type="info" :bordered="false" style="margin-top: 12px">
        模板只存学科，教师在一键排课时按「任课关系」自动带出。编辑模板不会影响已生成的课程记录，需对目标周重新应用。
      </n-alert>
    </n-spin>

    <!-- 单元格编辑 -->
    <n-modal v-model:show="cellModal">
      <n-card
        style="width: 480px; max-width: 92vw"
        :title="`编辑 周${['一','二','三','四','五','六','日'][cellForm.weekday - 1]} ${cellForm.slotName}`"
      >
        <n-form>
          <n-form-item label="学科">
            <SubjectPicker v-model="cellForm.subject" :subjects="subjects" />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button type="error" ghost @click="clearCell">清空该格</n-button>
            <n-button @click="cellModal = false">取消</n-button>
            <n-button type="primary" @click="saveCell">保存</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>

    <!-- 新建空白模板 -->
    <n-modal v-model:show="createModal">
      <n-card style="width: 420px" title="新建空白模板">
        <n-form>
          <n-form-item label="名称"><n-input v-model:value="createForm.name" /></n-form-item>
          <n-form-item label="备注"><n-input v-model:value="createForm.note" /></n-form-item>
          <n-form-item label="设为默认"><n-switch v-model:value="createForm.is_default" /></n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="createModal = false">取消</n-button>
            <n-button type="primary" @click="doCreate">创建</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>

    <!-- 从某周生成 -->
    <n-modal v-model:show="fromWeekModal">
      <n-card style="width: 440px" title="从某周生成模板">
        <n-form>
          <n-form-item label="名称"><n-input v-model:value="fromWeekForm.name" /></n-form-item>
          <n-form-item label="备注"><n-input v-model:value="fromWeekForm.note" /></n-form-item>
          <n-form-item label="起始周一">
            <n-date-picker
              v-model:formatted-value="fromWeekForm.monday"
              type="date"
              value-format="yyyy-MM-dd"
              :is-date-disabled="isDateDisabled"
            />
          </n-form-item>
          <n-form-item label="设为默认">
            <n-switch v-model:value="fromWeekForm.is_default" />
          </n-form-item>
          <n-alert type="warning" :bordered="false">
            将把该周（周一~周日）全部班级的课程记录另存为模板。
          </n-alert>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="fromWeekModal = false">取消</n-button>
            <n-button type="primary" @click="doCreateFromWeek">保存</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>

    <!-- 模板信息 -->
    <n-modal v-model:show="infoModal">
      <n-card style="width: 420px" title="模板信息">
        <n-form>
          <n-form-item label="名称"><n-input v-model:value="infoForm.name" /></n-form-item>
          <n-form-item label="备注"><n-input v-model:value="infoForm.note" /></n-form-item>
          <n-form-item label="设为默认"><n-switch v-model:value="infoForm.is_default" /></n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="infoModal = false">取消</n-button>
            <n-button type="primary" @click="saveInfo">保存</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>

    <!-- 复制周X到周Y -->
    <n-modal v-model:show="copyModal">
      <n-card style="width: 420px" title="复制某天到另一天（本班）">
        <n-form>
          <n-form-item label="源">
            <n-select
              v-model:value="copyForm.source"
              :options="WEEKDAY_NAMES.map((n, i) => ({ label: n, value: i + 1 }))"
            />
          </n-form-item>
          <n-form-item label="目标">
            <n-select
              v-model:value="copyForm.target"
              :options="WEEKDAY_NAMES.map((n, i) => ({ label: n, value: i + 1 }))"
            />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="copyModal = false">取消</n-button>
            <n-button type="primary" @click="doCopyWeekday">复制</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>

    <!-- 应用模板 -->
    <n-modal v-model:show="applyModal">
      <n-card style="width: 440px" title="应用模板到某周">
        <n-form>
          <n-form-item label="起始周一">
            <n-date-picker
              v-model:formatted-value="applyForm.monday"
              type="date"
              value-format="yyyy-MM-dd"
              :is-date-disabled="isDateDisabled"
            />
          </n-form-item>
          <n-form-item label="覆盖该周">
            <n-switch v-model:value="applyForm.overwrite" />
          </n-form-item>
          <n-alert type="info" :bordered="false">
            将按模板生成该周的课程记录。锁定日期会整体拒绝执行。
          </n-alert>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="applyModal = false">取消</n-button>
            <n-button type="primary" @click="doApply">开始排课</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>
  </div>
</template>
