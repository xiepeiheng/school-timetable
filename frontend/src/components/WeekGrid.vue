<script setup lang="ts">
export interface GridColumn {
  key: string
  label: string
  sub?: string
}
export interface GridCell {
  main: string
  sub?: string
  color?: string
}
interface Slot {
  id: number
  name: string
}

const props = defineProps<{
  slots: Slot[]
  columns: GridColumn[]
  cell: (columnKey: string, slotId: number) => GridCell | undefined
  blocked?: (columnKey: string) => boolean
}>()

const emit = defineEmits<{
  (e: "cell-click", columnKey: string, slot: Slot): void
}>()
</script>

<template>
  <div style="overflow: auto">
    <table class="tt-grid">
      <thead>
        <tr>
          <th class="slot-col">时间段</th>
          <th v-for="c in props.columns" :key="c.key">
            {{ c.label }}
            <template v-if="c.sub"><br /><small>{{ c.sub }}</small></template>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="slot in props.slots" :key="slot.id">
          <td class="slot-col">{{ slot.name }}</td>
          <td
            v-for="c in props.columns"
            :key="c.key + '-' + slot.id"
            class="cell"
            :class="{ blocked: props.blocked && props.blocked(c.key) }"
            @click="emit('cell-click', c.key, slot)"
          >
            <template v-if="props.cell(c.key, slot.id)">
              <div
                class="subject"
                :style="{ color: props.cell(c.key, slot.id)!.color || undefined }"
              >
                {{ props.cell(c.key, slot.id)!.main }}
              </div>
              <small>{{ props.cell(c.key, slot.id)!.sub || "" }}</small>
            </template>
            <span v-else class="empty">—</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.tt-grid {
  border-collapse: collapse;
  width: 100%;
  table-layout: fixed;
  background: #fff;
}
.tt-grid th,
.tt-grid td {
  border: 1px solid #e0e0e6;
  padding: 4px 2px;
  text-align: center;
  font-size: 13px;
  overflow: hidden;
  word-break: break-all;
}
.tt-grid th {
  background: #fafafc;
  position: sticky;
  top: 0;
}
.slot-col {
  width: 64px;
  background: #fafafc;
  font-weight: 600;
}
.cell {
  cursor: pointer;
  height: 46px;
  vertical-align: middle;
}
.cell:hover {
  background: #f0f7ff;
}
.cell.blocked {
  background: #f7f7f7;
  cursor: not-allowed;
}
.subject {
  font-weight: 600;
}
.empty {
  color: #ccc;
}
small {
  color: #888;
}
</style>
