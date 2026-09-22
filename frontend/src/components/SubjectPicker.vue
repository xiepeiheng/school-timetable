<script setup lang="ts">
import type { Subject } from "@/api/base/type"

const props = defineProps<{
  modelValue: number | null
  subjects: Subject[]
}>()

const emit = defineEmits<{
  (e: "update:modelValue", value: number | null): void
}>()
</script>

<template>
  <div class="picker-grid">
    <n-button
      v-for="s in props.subjects"
      :key="s.id"
      :type="props.modelValue === s.id ? 'primary' : 'default'"
      @click="emit('update:modelValue', s.id)"
    >
      {{ s.name }}
    </n-button>
    <n-button
      quaternary
      :disabled="props.modelValue === null"
      @click="emit('update:modelValue', null)"
    >
      清除
    </n-button>
  </div>
</template>

<style scoped>
.picker-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
