<script setup lang="ts">
import { computed } from "vue"
import type { Teacher } from "@/api/base/type"

const props = defineProps<{
  modelValue: number | null
  teachers: Teacher[]
  subjectId: number | null
}>()

const emit = defineEmits<{
  (e: "update:modelValue", value: number | null): void
}>()

/** 与当前学科相同的老师排在前面，其余按姓名排序。 */
const sorted = computed(() =>
  [...props.teachers].sort((a, b) => {
    const am = a.subject === props.subjectId ? 0 : 1
    const bm = b.subject === props.subjectId ? 0 : 1
    if (am !== bm) return am - bm
    return a.name.localeCompare(b.name, "zh")
  }),
)
</script>

<template>
  <div class="teacher-list">
    <button
      class="t-item"
      :class="{ active: props.modelValue === null }"
      @click="emit('update:modelValue', null)"
    >
      <span>未指定</span>
    </button>
    <button
      v-for="t in sorted"
      :key="t.id"
      class="t-item"
      :class="{ active: props.modelValue === t.id }"
      @click="emit('update:modelValue', t.id)"
    >
      <span>{{ t.name }}</span>
      <span class="subj">{{ t.subject_name }}</span>
    </button>
  </div>
</template>

<style scoped>
.teacher-list {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-height: 320px;
  overflow-y: auto;
  border: 1px solid #eee;
  border-radius: 4px;
}
.t-item {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  min-height: 46px;
  align-items: center;
  padding: 10px 16px;
  border: none;
  border-bottom: 1px solid #f2f2f2;
  background: #fff;
  font-size: 15px;
  text-align: left;
  cursor: pointer;
}
.t-item:last-child {
  border-bottom: none;
}
.t-item.active {
  background: #e8f2ff;
  color: #2080f0;
  font-weight: 600;
}
.subj {
  color: #999;
  font-weight: 400;
}
</style>
