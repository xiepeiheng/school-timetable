<script setup lang="ts">
import { computed, onMounted, ref, type Ref } from "vue"
import { useRouter } from "vue-router"
import { useDialog, useMessage } from "naive-ui"
import {
  reqAssignmentList,
  reqClassList,
  reqSubjectList,
  reqTeacherList,
  reqTimeSlotList,
} from "@/api/base"
import type {
  SchoolClass,
  Subject,
  Teacher,
  TeachingAssignment,
  TimeSlot,
} from "@/api/base/type"
import {
  reqSessionBulk,
  reqSessionClear,
  reqSessionCopyDay,
  reqSessionList,
  reqSessionSwap,
  reqTemplateApply,
  reqTemplateCreateFromWeek,
  reqTemplateList,
} from "@/api/timetable"
import type { CourseSession, ScheduleTemplate } from "@/api/timetable/type"
import WeekGrid, {
  type GridCell,
  type GridColumn,
} from "@/components/WeekGrid.vue"
import SubjectPicker from "@/components/SubjectPicker.vue"
import TeacherPicker from "@/components/TeacherPicker.vue"
import { addDays, getMonday, WEEKDAY_NAMES, weekDates } from "@/utils/dates"

const message = useMessage()
const dialog = useDialog()
const router = useRouter()

const FLAG_OPTIONS = [
  { label: "正常", value: "normal" },
  { label: "换课", value: "swap" },
  { label: "代课", value: "substitute" },
  { label: "异常", value: "abnormal" },
]
const FLAG_LABEL: Record<string, string> = {
  swap: "换课",
  substitute: "代课",
  abnormal: "异常",
}
const FLAG_BORDER: Record<string, string> = {
  swap: "#FB8C00",
  substitute: "#1E88E5",
  abnormal: "#E53935",
}

const TEACHING_SLOT_NAMES = [
  "早读",
  "一",
  "二",
  "三",
  "四",
  "五",
  "六",
  "七",
  "八",
  "晚一",
  "晚二",
  "晚三",
]

type ClassMode = "current" | "all" | "custom"
interface ScopeForm {
  classMode: ClassMode
  classIds: number[]
  slotIds: number[]
}

const slots = ref<TimeSlot[]>([])
const subjects = ref<Subject[]>([])
const teachers = ref<Teacher[]>([])
const classes = ref<SchoolClass[]>([])
const assignments = ref<TeachingAssignment[]>([])
const templates = ref<ScheduleTemplate[]>([])
const sessions = ref<Record<string, CourseSession>>({})

const monday = ref(getMonday(new Date()))
const selectedClass = ref<number | null>(null)
const loading = ref(false)

const weekDays = computed(() => weekDates(monday.value))
const activeSlots = computed(() => slots.value.filter((s) => s.is_active))
const teachingSlots = computed(() =>
  activeSlots.value.filter((s) => TEACHING_SLOT_NAMES.includes(s.name)),
)
const subjectMap = computed(() =>
  Object.fromEntries(subjects.value.map((s) => [s.id, s])),
)
const classOptions = computed(() =>
  classes.value.map((c) => ({ label: c.name, value: c.id })),
)
const defaultTeacher = computed(() => {
  const map: Record<string, number> = {}
  for (const a of assignments.value) map[`${a.school_class}-${a.subject}`] = a.teacher
  return map
})

function allSlotIds() {
  return teachingSlots.value.map((s) => s.id)
}

function allSlotsComputed(form: Ref<{ slotIds: number[] }>) {
  return computed({
    get: () =>
      teachingSlots.value.length > 0 &&
      form.value.slotIds.length === teachingSlots.value.length,
    set: (v: boolean) => {
      form.value.slotIds = v ? allSlotIds() : []
    },
  })
}

function resolveClassIds(mode: ClassMode, ids: number[]): number[] | undefined {
  if (mode === "current") return selectedClass.value ? [selectedClass.value] : []
  if (mode === "custom") return ids
  return undefined // 全体
}

function classScopeLabel(mode: ClassMode, ids: number[]): string {
  if (mode === "current") {
    const name = classes.value.find((c) => c.id === selectedClass.value)?.name
    return `当前班（${name || "—"}）`
  }
  if (mode === "custom") return `自选 ${ids.length} 个班`
  return "全体班级"
}

function slotScopeLabel(slotIds: number[]): string {
  if (slotIds.length === teachingSlots.value.length) return "全部时段"
  return teachingSlots.value
    .filter((s) => slotIds.includes(s.id))
    .map((s) => s.name)
    .join("、")
}

function cellKey(date: string, slotId: number) {
  return `${selectedClass.value}-${date}-${slotId}`
}

function cellSession(date: string, slotId: number) {
  return sessions.value[cellKey(date, slotId)]
}

async function loadBase() {
  const [sl, sub, tea, cls, asg, tpl] = await Promise.all([
    reqTimeSlotList(),
    reqSubjectList(),
    reqTeacherList({ size: 500 }),
    reqClassList({ size: 500 }),
    reqAssignmentList({ size: 500 }),
    reqTemplateList(),
  ])
  slots.value = sl.data
  subjects.value = sub.data
  teachers.value = tea.data.items
  classes.value = cls.data.items
  assignments.value = asg.data.items
  templates.value = tpl.data.items
  if (!selectedClass.value && classes.value.length) {
    selectedClass.value = classes.value[0].id
  }
}

async function loadWeek() {
  if (!selectedClass.value) return
  loading.value = true
  try {
    const start = monday.value
    const end = addDays(start, 6)
    // 只取当前班级（约 60 条），避免整周 9 个班超过分页上限而漏数据
    const res = await reqSessionList({
      date_from: start,
      date_to: end,
      school_class: selectedClass.value,
      size: 500,
    })
    const map: Record<string, CourseSession> = {}
    for (const s of res.data.items) {
      map[`${s.school_class}-${s.date}-${s.time_slot}`] = s
    }
    sessions.value = map
  } finally {
    loading.value = false
  }
}

async function reload() {
  await loadWeek()
}

function shiftWeek(delta: number) {
  monday.value = addDays(monday.value, delta * 7)
  reload()
}

// 只允许选择周一：课表以整周为单位
function isDateDisabled(timestamp: number) {
  return new Date(timestamp).getDay() !== 1
}

// ── 网格 ──
const gridColumns = computed<GridColumn[]>(() =>
  weekDays.value.map((d, i) => ({
    key: d,
    label: WEEKDAY_NAMES[i],
    sub: d.slice(5),
  })),
)

function gridCell(columnKey: string, slotId: number): GridCell | undefined {
  const session = cellSession(columnKey, slotId)
  if (!session) return undefined
  const marks: string[] = []
  if (session.flag && session.flag !== "normal")
    marks.push(FLAG_LABEL[session.flag] || "异常")
  const sub = [session.teacher_name || "未指定", ...marks].join(" ")
  return {
    main: session.subject_name,
    sub,
    color: subjectMap.value[session.subject]?.color,
    borderColor:
      session.flag && session.flag !== "normal"
        ? FLAG_BORDER[session.flag]
        : undefined,
  }
}

function onCellClick(columnKey: string, slot: { id: number; name: string }) {
  openCell(columnKey, slot as TimeSlot)
}

// ── 单元格编辑 ──
const cellModal = ref(false)
const cellForm = ref<{
  date: string
  slotId: number
  slotName: string
  subject: number | null
  teacher: number | null
  flag: string
  note: string
}>({
  date: "",
  slotId: 0,
  slotName: "",
  subject: null,
  teacher: null,
  flag: "normal",
  note: "",
})

function openCell(date: string, slot: TimeSlot) {
  const existing = cellSession(date, slot.id)
  cellForm.value = {
    date,
    slotId: slot.id,
    slotName: slot.name,
    subject: existing?.subject ?? null,
    teacher: existing?.teacher ?? null,
    flag: existing?.flag ?? "normal",
    note: existing?.note ?? "",
  }
  cellModal.value = true
}

function onSubjectChange(v: number | null) {
  cellForm.value.subject = v
  if (v && selectedClass.value) {
    const def = defaultTeacher.value[`${selectedClass.value}-${v}`]
    if (def) cellForm.value.teacher = def
  }
}

async function saveCell() {
  if (!selectedClass.value) return
  await reqSessionBulk([
    {
      date: cellForm.value.date,
      time_slot: cellForm.value.slotId,
      school_class: selectedClass.value,
      subject: cellForm.value.subject,
      teacher: cellForm.value.teacher,
      flag: cellForm.value.flag,
      note: cellForm.value.note,
    },
  ])
  message.success("已保存")
  cellModal.value = false
  reload()
}

async function clearCell() {
  cellForm.value.subject = null
  cellForm.value.note = ""
  await saveCell()
}

// ── 二次确认 ──
function confirmDanger(content: string, onOk: () => unknown) {
  dialog.warning({
    title: "请确认",
    content,
    positiveText: "确定",
    negativeText: "取消",
    onPositiveClick: () => {
      void onOk()
    },
  })
}

// ── 一键排课 ──
const applyModal = ref(false)
const applyForm = ref({ template: null as number | null, overwrite: true })
async function doApply() {
  if (!applyForm.value.template) return message.warning("请选择模板")
  const res = await reqTemplateApply({
    template: applyForm.value.template,
    start_date: monday.value,
    end_date: addDays(monday.value, 6),
    overwrite: applyForm.value.overwrite,
  })
  message.success(`排课完成：新增 ${res.data.created}，跳过 ${res.data.skipped}`)
  applyModal.value = false
  reload()
}
function confirmApply() {
  if (!applyForm.value.template) return message.warning("请选择模板")
  const label = applyForm.value.overwrite ? "覆盖" : "仅补空"
  confirmDanger(
    `将按模板（${label}）生成 ${monday.value} ~ ${addDays(monday.value, 6)} 的课程记录，确定继续？`,
    doApply,
  )
}

// ── 存为模板 ──
const tplModal = ref(false)
const tplForm = ref({ name: "", note: "", is_default: false })
async function saveTemplate() {
  if (!tplForm.value.name) return message.warning("请填写模板名称")
  await reqTemplateCreateFromWeek({
    name: tplForm.value.name,
    note: tplForm.value.note,
    start_date: monday.value,
    end_date: addDays(monday.value, 6),
    is_default: tplForm.value.is_default,
  })
  message.success("模板已保存")
  tplModal.value = false
  tplForm.value = { name: "", note: "", is_default: false }
  templates.value = (await reqTemplateList()).data.items
}

// ── 挖空 / 清空 ──
const clearModal = ref(false)
const clearForm = ref<
  { start_date: string | null; end_date: string | null } & ScopeForm
>({
  start_date: monday.value,
  end_date: addDays(monday.value, 6),
  classMode: "current",
  classIds: [],
  slotIds: [],
})
const clearAllSlots = allSlotsComputed(clearForm)

function openClear() {
  clearForm.value = {
    start_date: monday.value,
    end_date: addDays(monday.value, 6),
    classMode: "current",
    classIds: [],
    slotIds: allSlotIds(),
  }
  clearModal.value = true
}

async function doClear() {
  const { start_date, end_date, classMode, classIds, slotIds } = clearForm.value
  if (!start_date || !end_date)
    return message.warning("请选择开始和结束日期")
  if (classMode === "custom" && !classIds.length)
    return message.warning("请选择要清空的班级")
  if (!slotIds.length) return message.warning("请至少选择一个时段")
  const res = await reqSessionClear({
    start_date,
    end_date,
    school_classes: resolveClassIds(classMode, classIds),
    time_slots: slotIds,
  })
  message.success(`已清空 ${res.data.deleted} 条`)
  clearModal.value = false
  reload()
}

function confirmClear() {
  const { start_date, end_date, classMode, classIds, slotIds } = clearForm.value
  if (!start_date || !end_date)
    return message.warning("请选择开始和结束日期")
  if (classMode === "custom" && !classIds.length)
    return message.warning("请选择要清空的班级")
  if (!slotIds.length) return message.warning("请至少选择一个时段")
  confirmDanger(
    `将对 ${classScopeLabel(classMode, classIds)} 清空 ${start_date} ~ ${end_date} 的「${slotScopeLabel(slotIds)}」，确定？`,
    doClear,
  )
}

// ── 套用某天的课 ──
const copyModal = ref(false)
const copyForm = ref<
  {
    source_date: string | null
    target_date: string | null
  } & ScopeForm
>({
  source_date: monday.value,
  target_date: null,
  classMode: "current",
  classIds: [],
  slotIds: [],
})
const copyAllSlots = allSlotsComputed(copyForm)

function openCopy() {
  copyForm.value = {
    source_date: monday.value,
    target_date: null,
    classMode: "current",
    classIds: [],
    slotIds: allSlotIds(),
  }
  copyModal.value = true
}

async function doCopy() {
  const { source_date, target_date, classMode, classIds, slotIds } =
    copyForm.value
  if (!source_date || !target_date)
    return message.warning("请选择源日期和目标日期")
  if (classMode === "custom" && !classIds.length)
    return message.warning("请选择要套用的班级")
  if (!slotIds.length) return message.warning("请至少选择一个时段")
  const res = await reqSessionCopyDay({
    source_date,
    target_date,
    school_classes: resolveClassIds(classMode, classIds),
    time_slots: slotIds,
  })
  message.success(`已套用 ${res.data.copied} 条`)
  copyModal.value = false
  reload()
}

function confirmCopy() {
  const { source_date, target_date, classMode, classIds, slotIds } =
    copyForm.value
  if (!source_date || !target_date)
    return message.warning("请选择源日期和目标日期")
  if (classMode === "custom" && !classIds.length)
    return message.warning("请选择要套用的班级")
  if (!slotIds.length) return message.warning("请至少选择一个时段")
  confirmDanger(
    `将把 ${source_date} 的「${slotScopeLabel(slotIds)}」套用到 ${classScopeLabel(classMode, classIds)} 的 ${target_date}，确定？`,
    doCopy,
  )
}

// ── 交换两节课 ──
const swapModal = ref(false)
interface SwapSide {
  date: string | null
  klass: number | null
  session: number | null
}
const swapA = ref<SwapSide>({ date: null, klass: null, session: null })
const swapB = ref<SwapSide>({ date: null, klass: null, session: null })
const swapAOptions = ref<{ label: string; value: number }[]>([])
const swapBOptions = ref<{ label: string; value: number }[]>([])

function openSwap() {
  swapA.value = { date: monday.value, klass: selectedClass.value, session: null }
  swapB.value = { date: monday.value, klass: selectedClass.value, session: null }
  swapAOptions.value = []
  swapBOptions.value = []
  swapModal.value = true
  loadSwapOptions("A")
  loadSwapOptions("B")
}

async function loadSwapOptions(side: "A" | "B") {
  const form = side === "A" ? swapA.value : swapB.value
  const target = side === "A" ? swapAOptions : swapBOptions
  form.session = null
  target.value = []
  if (!form.date || !form.klass) return
  const res = await reqSessionList({
    date_from: form.date,
    date_to: form.date,
    school_class: form.klass,
    size: 500,
  })
  target.value = res.data.items.map((s) => ({
    label: `${s.time_slot_name} · ${s.subject_name} · ${s.teacher_name || "未指定"}`,
    value: s.id,
  }))
}

async function doSwap() {
  const a = swapA.value.session
  const b = swapB.value.session
  if (!a || !b) return message.warning("请为两侧各选择一节课")
  if (a === b) return message.warning("两侧不能是同一节课")
  await reqSessionSwap([a, b])
  message.success("已交换，两格已标记为换课")
  swapModal.value = false
  reload()
}

onMounted(async () => {
  await loadBase()
  await loadWeek()
})
</script>

<template>
  <div>
    <h3 class="page-title">排课</h3>
    <div class="toolbar">
      <n-button @click="shiftWeek(-1)">上一周</n-button>
      <n-date-picker
        v-model:formatted-value="monday"
        type="date"
        value-format="yyyy-MM-dd"
        :is-date-disabled="isDateDisabled"
        @update:formatted-value="(v: string | null) => { monday = getMonday(v || new Date()); reload() }"
      />
      <n-button @click="shiftWeek(1)">下一周</n-button>
      <n-button @click="monday = getMonday(new Date()); reload()">本周</n-button>
      <span style="margin-left: 12px">班级：</span>
      <n-select
        v-model:value="selectedClass"
        :options="classOptions"
        style="width: 140px"
        @update:value="reload"
      />
    </div>

    <div class="toolbar">
      <n-button type="primary" @click="applyModal = true">一键排课</n-button>
      <n-button @click="tplModal = true">存为模板</n-button>
      <n-button @click="router.push({ name: 'templates' })">模板管理</n-button>
      <n-button @click="openSwap">交换两节课</n-button>
      <n-button @click="openCopy">套用某天的课</n-button>
      <n-button type="error" ghost @click="openClear">挖空 / 清空</n-button>
      <n-button @click="reload">刷新</n-button>
    </div>

    <div class="legend">
      <span>图例：</span>
      <span class="legend-item"><i style="background: #fb8c00"></i>换课</span>
      <span class="legend-item"><i style="background: #1e88e5"></i>代课</span>
      <span class="legend-item"><i style="background: #e53935"></i>异常</span>
    </div>

    <n-spin :show="loading">
      <WeekGrid
        :slots="activeSlots"
        :columns="gridColumns"
        :cell="gridCell"
        @cell-click="onCellClick"
      />
    </n-spin>

    <!-- 单元格编辑 -->
    <n-modal v-model:show="cellModal">
      <n-card
        style="width: 560px; max-width: 92vw"
        :title="`编辑 ${cellForm.date} ${cellForm.slotName}`"
      >
        <n-form>
          <n-form-item label="学科">
            <SubjectPicker
              :model-value="cellForm.subject"
              :subjects="subjects"
              @update:model-value="onSubjectChange"
            />
          </n-form-item>
          <n-form-item label="教师">
            <TeacherPicker
              v-model="cellForm.teacher"
              :teachers="teachers"
              :subject-id="cellForm.subject"
            />
          </n-form-item>
          <n-form-item label="标记">
            <n-select
              v-model:value="cellForm.flag"
              :options="FLAG_OPTIONS"
              style="width: 160px"
            />
            <span style="margin-left: 8px; color: #999">换课/代课/异常，可留备注</span>
          </n-form-item>
          <n-form-item label="备注">
            <n-input
              v-model:value="cellForm.note"
              type="textarea"
              :rows="2"
              placeholder="可写调课说明等，留空即可"
            />
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

    <!-- 交换两节课 -->
    <n-modal v-model:show="swapModal">
      <n-card style="width: 640px; max-width: 94vw" title="交换两节课">
        <n-alert type="info" :bordered="false" style="margin-bottom: 12px">
          交换只改「学科 + 教师」，日期/班级/时段/权重不变；两格会自动标记为换课并写下备注。
        </n-alert>
        <div class="swap-row">
          <span class="swap-label">A</span>
          <n-date-picker
            v-model:formatted-value="swapA.date"
            type="date"
            value-format="yyyy-MM-dd"
            style="width: 150px"
            @update:formatted-value="loadSwapOptions('A')"
          />
          <n-select
            v-model:value="swapA.klass"
            :options="classOptions"
            placeholder="班级"
            style="width: 110px"
            @update:value="loadSwapOptions('A')"
          />
          <n-select
            v-model:value="swapA.session"
            :options="swapAOptions"
            placeholder="选择课程"
            style="flex: 1"
          />
        </div>
        <div class="swap-row">
          <span class="swap-label">B</span>
          <n-date-picker
            v-model:formatted-value="swapB.date"
            type="date"
            value-format="yyyy-MM-dd"
            style="width: 150px"
            @update:formatted-value="loadSwapOptions('B')"
          />
          <n-select
            v-model:value="swapB.klass"
            :options="classOptions"
            placeholder="班级"
            style="width: 110px"
            @update:value="loadSwapOptions('B')"
          />
          <n-select
            v-model:value="swapB.session"
            :options="swapBOptions"
            placeholder="选择课程"
            style="flex: 1"
          />
        </div>
        <template #footer>
          <n-space justify="end">
            <n-button @click="swapModal = false">取消</n-button>
            <n-button type="primary" @click="doSwap">交换</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>

    <!-- 一键排课 -->
    <n-modal v-model:show="applyModal">
      <n-card style="width: 440px" title="一键排课（当前周）">
        <n-form>
          <n-form-item label="模板">
            <n-select
              v-model:value="applyForm.template"
              :options="templates.map((t) => ({ label: t.name, value: t.id }))"
            />
          </n-form-item>
          <n-form-item label="覆盖本周">
            <n-switch v-model:value="applyForm.overwrite" />
          </n-form-item>
          <n-alert type="info" :bordered="false">
            将按模板生成 {{ monday }} ~ {{ addDays(monday, 6) }} 的课程记录。
          </n-alert>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="applyModal = false">取消</n-button>
            <n-button type="primary" @click="confirmApply">开始排课</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>

    <!-- 存为模板 -->
    <n-modal v-model:show="tplModal">
      <n-card style="width: 440px" title="把当前周存为模板">
        <n-form>
          <n-form-item label="模板名称">
            <n-input v-model:value="tplForm.name" />
          </n-form-item>
          <n-form-item label="备注">
            <n-input v-model:value="tplForm.note" />
          </n-form-item>
          <n-form-item label="设为默认">
            <n-switch v-model:value="tplForm.is_default" />
          </n-form-item>
          <n-alert type="warning" :bordered="false">
            范围必须是完整周一~周日，将保存全体班级。
          </n-alert>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="tplModal = false">取消</n-button>
            <n-button type="primary" @click="saveTemplate">保存</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>

    <!-- 挖空 / 清空 -->
    <n-modal v-model:show="clearModal">
      <n-card style="width: 560px; max-width: 94vw" title="挖空 / 清空">
        <n-form>
          <n-form-item label="班级范围">
            <n-radio-group v-model:value="clearForm.classMode">
              <n-space>
                <n-radio value="current">当前班</n-radio>
                <n-radio value="all">全体</n-radio>
                <n-radio value="custom">自选</n-radio>
              </n-space>
            </n-radio-group>
          </n-form-item>
          <n-form-item v-if="clearForm.classMode === 'custom'" label="选择班级">
            <n-select v-model:value="clearForm.classIds" :options="classOptions" multiple />
          </n-form-item>
          <n-form-item label="日期范围">
            <n-space align="center">
              <n-date-picker v-model:formatted-value="clearForm.start_date" value-format="yyyy-MM-dd" />
              <span>~</span>
              <n-date-picker v-model:formatted-value="clearForm.end_date" value-format="yyyy-MM-dd" />
            </n-space>
          </n-form-item>
          <n-form-item label="时段">
            <div style="width: 100%">
              <n-checkbox v-model:checked="clearAllSlots">全选</n-checkbox>
              <n-checkbox-group v-model:value="clearForm.slotIds" style="margin-top: 8px">
                <n-space>
                  <n-checkbox
                    v-for="s in teachingSlots"
                    :key="s.id"
                    :value="s.id"
                    :label="s.name"
                  />
                </n-space>
              </n-checkbox-group>
            </div>
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="clearModal = false">取消</n-button>
            <n-button type="error" @click="confirmClear">清空</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>

    <!-- 套用某天的课 -->
    <n-modal v-model:show="copyModal">
      <n-card style="width: 560px; max-width: 94vw" title="套用某天的课">
        <n-form>
          <n-form-item label="班级范围">
            <n-radio-group v-model:value="copyForm.classMode">
              <n-space>
                <n-radio value="current">当前班</n-radio>
                <n-radio value="all">全体</n-radio>
                <n-radio value="custom">自选</n-radio>
              </n-space>
            </n-radio-group>
          </n-form-item>
          <n-form-item v-if="copyForm.classMode === 'custom'" label="选择班级">
            <n-select v-model:value="copyForm.classIds" :options="classOptions" multiple />
          </n-form-item>
          <n-form-item label="源日期">
            <n-date-picker v-model:formatted-value="copyForm.source_date" value-format="yyyy-MM-dd" />
          </n-form-item>
          <n-form-item label="目标日期">
            <n-date-picker v-model:formatted-value="copyForm.target_date" value-format="yyyy-MM-dd" />
          </n-form-item>
          <n-form-item label="时段">
            <div style="width: 100%">
              <n-checkbox v-model:checked="copyAllSlots">全选</n-checkbox>
              <n-checkbox-group v-model:value="copyForm.slotIds" style="margin-top: 8px">
                <n-space>
                  <n-checkbox
                    v-for="s in teachingSlots"
                    :key="s.id"
                    :value="s.id"
                    :label="s.name"
                  />
                </n-space>
              </n-checkbox-group>
            </div>
          </n-form-item>
          <n-alert type="warning" :bordered="false">
            会把「源日期」所选时段的课，覆盖到「目标日期」所选范围（目标这些格先清空再套用）。
          </n-alert>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="copyModal = false">取消</n-button>
            <n-button type="primary" @click="confirmCopy">套用</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>
  </div>
</template>

<style scoped>
.swap-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.swap-label {
  width: 18px;
  font-weight: 700;
}
.legend {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 10px;
  font-size: 13px;
  color: #666;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.legend-item i {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 2px;
}
</style>
