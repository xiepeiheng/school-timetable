<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { useMessage } from "naive-ui"
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
  reqLockGet,
  reqSessionBulk,
  reqSessionClear,
  reqSessionCopyDay,
  reqSessionList,
  reqSessionSyncClass,
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
import { addDays, fmt, getMonday, WEEKDAY_NAMES, weekDates } from "@/utils/dates"

const message = useMessage()
const router = useRouter()

const slots = ref<TimeSlot[]>([])
const subjects = ref<Subject[]>([])
const teachers = ref<Teacher[]>([])
const classes = ref<SchoolClass[]>([])
const assignments = ref<TeachingAssignment[]>([])
const templates = ref<ScheduleTemplate[]>([])
const sessions = ref<Record<string, CourseSession>>({})
const lockedThrough = ref<string | null>(null)

const monday = ref(getMonday(new Date()))
const selectedClass = ref<number | null>(null)
const loading = ref(false)

const weekDays = computed(() => weekDates(monday.value))
const activeSlots = computed(() => slots.value.filter((s) => s.is_active))
const subjectMap = computed(() =>
  Object.fromEntries(subjects.value.map((s) => [s.id, s])),
)
const teacherMap = computed(() =>
  Object.fromEntries(teachers.value.map((t) => [t.id, t])),
)
const defaultTeacher = computed(() => {
  const map: Record<string, number> = {}
  for (const a of assignments.value) map[`${a.school_class}-${a.subject}`] = a.teacher
  return map
})

function cellKey(date: string, slotId: number) {
  return `${selectedClass.value}-${date}-${slotId}`
}

function cellSession(date: string, slotId: number) {
  return sessions.value[cellKey(date, slotId)]
}

async function loadBase() {
  const [sl, sub, tea, cls, asg, tpl, lock] = await Promise.all([
    reqTimeSlotList(),
    reqSubjectList(),
    reqTeacherList({ size: 500 }),
    reqClassList({ size: 500 }),
    reqAssignmentList({ size: 500 }),
    reqTemplateList(),
    reqLockGet(),
  ])
  slots.value = sl.data
  subjects.value = sub.data
  teachers.value = tea.data.items
  classes.value = cls.data.items
  assignments.value = asg.data.items
  templates.value = tpl.data.items
  lockedThrough.value = lock.data.locked_through
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

function isWeekLocked(columnKey: string) {
  return !!lockedThrough.value && columnKey <= lockedThrough.value
}

function gridCell(columnKey: string, slotId: number): GridCell | undefined {
  const session = cellSession(columnKey, slotId)
  if (!session) return undefined
  return {
    main: session.subject_name,
    sub: session.teacher_name || "未指定",
    color: subjectMap.value[session.subject]?.color,
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
}>({ date: "", slotId: 0, slotName: "", subject: null, teacher: null })

function openCell(date: string, slot: TimeSlot) {
  const existing = cellSession(date, slot.id)
  cellForm.value = {
    date,
    slotId: slot.id,
    slotName: slot.name,
    subject: existing?.subject ?? null,
    teacher: existing?.teacher ?? null,
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
    },
  ])
  message.success("已保存")
  cellModal.value = false
  reload()
}

async function clearCell() {
  cellForm.value.subject = null
  await saveCell()
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

// ── 清空 ──
const clearModal = ref(false)
const clearForm = ref({ start_date: monday.value, end_date: addDays(monday.value, 6) })
async function doClear() {
  const res = await reqSessionClear(clearForm.value)
  message.success(`已清空 ${res.data.deleted} 条`)
  clearModal.value = false
  reload()
}

// ── 复制单日 ──
const copyModal = ref(false)
const copyForm = ref({ source_date: "", target_date: "" })
async function doCopy() {
  if (!copyForm.value.source_date || !copyForm.value.target_date)
    return message.warning("请选择源日期和目标日期")
  const res = await reqSessionCopyDay(copyForm.value)
  message.success(`已复制 ${res.data.copied} 条`)
  copyModal.value = false
  reload()
}

// ── 班级同步 ──
const syncModal = ref(false)
const syncForm = ref({
  source_date: "",
  source_class: null as number | null,
  target_classes: [] as number[],
})
async function doSync() {
  if (!syncForm.value.source_date || !syncForm.value.source_class)
    return message.warning("请选择源日期和源班级")
  const res = await reqSessionSyncClass({
    source_date: syncForm.value.source_date,
    source_class: syncForm.value.source_class,
    target_classes: syncForm.value.target_classes,
  })
  message.success(`已同步到 ${res.data.target_classes} 个班，共 ${res.data.copied} 条`)
  syncModal.value = false
  reload()
}

const classOptions = computed(() =>
  classes.value.map((c) => ({ label: c.name, value: c.id })),
)

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
      <n-tag v-if="lockedThrough" type="warning">已锁定至 {{ lockedThrough }}</n-tag>
    </div>

    <div class="toolbar">
      <n-button type="primary" @click="applyModal = true">一键排课</n-button>
      <n-button @click="tplModal = true">存为模板</n-button>
      <n-button @click="router.push({ name: 'templates' })">模板管理</n-button>
      <n-button @click="copyModal = true">复制单日</n-button>
      <n-button @click="syncModal = true">班级同步</n-button>
      <n-button type="error" ghost @click="clearModal = true">清空</n-button>
      <n-button @click="reload">刷新</n-button>
    </div>

    <n-spin :show="loading">
      <WeekGrid
        :slots="activeSlots"
        :columns="gridColumns"
        :cell="gridCell"
        :blocked="isWeekLocked"
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
            将按模板生成 {{ monday }} ~ {{ addDays(monday, 6) }} 的课程记录。若所选周包含已锁定日期，将整体拒绝执行。
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

    <!-- 清空 -->
    <n-modal v-model:show="clearModal">
      <n-card style="width: 440px" title="清空课程记录">
        <n-form>
          <n-form-item label="开始日期">
            <n-date-picker v-model:formatted-value="clearForm.start_date" value-format="yyyy-MM-dd" />
          </n-form-item>
          <n-form-item label="结束日期">
            <n-date-picker v-model:formatted-value="clearForm.end_date" value-format="yyyy-MM-dd" />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="clearModal = false">取消</n-button>
            <n-button type="error" @click="doClear">清空</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>

    <!-- 复制单日 -->
    <n-modal v-model:show="copyModal">
      <n-card style="width: 440px" title="复制单日">
        <n-form>
          <n-form-item label="源日期">
            <n-date-picker v-model:formatted-value="copyForm.source_date" value-format="yyyy-MM-dd" />
          </n-form-item>
          <n-form-item label="目标日期">
            <n-date-picker v-model:formatted-value="copyForm.target_date" value-format="yyyy-MM-dd" />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="copyModal = false">取消</n-button>
            <n-button type="primary" @click="doCopy">复制</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>

    <!-- 班级同步 -->
    <n-modal v-model:show="syncModal">
      <n-card style="width: 480px" title="把一个班的某天同步到其他班">
        <n-form>
          <n-form-item label="源日期">
            <n-date-picker v-model:formatted-value="syncForm.source_date" value-format="yyyy-MM-dd" />
          </n-form-item>
          <n-form-item label="源班级">
            <n-select v-model:value="syncForm.source_class" :options="classOptions" />
          </n-form-item>
          <n-form-item label="目标班级（留空=其余全部）">
            <n-select
              v-model:value="syncForm.target_classes"
              :options="classOptions"
              multiple
            />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="syncModal = false">取消</n-button>
            <n-button type="primary" @click="doSync">同步</n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>
  </div>
</template>

