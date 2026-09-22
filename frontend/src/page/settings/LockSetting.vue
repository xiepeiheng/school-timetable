<script setup lang="ts">
import { onMounted, ref } from "vue"
import { useMessage } from "naive-ui"
import { reqLockClear, reqLockGet, reqLockSet } from "@/api/timetable"

const message = useMessage()
const lockedThrough = ref<string | null>(null)
const pick = ref<string | null>(null)

async function load() {
  const res = await reqLockGet()
  lockedThrough.value = res.data.locked_through
  pick.value = res.data.locked_through
}

async function save() {
  const res = await reqLockSet(pick.value)
  lockedThrough.value = res.data.locked_through
  message.success("锁定已更新")
}

async function clear() {
  await reqLockClear()
  lockedThrough.value = null
  pick.value = null
  message.success("锁定已取消")
}

onMounted(load)
</script>

<template>
  <div>
    <h3 class="page-title">锁定设置</h3>
    <n-card style="max-width: 560px">
      <n-alert type="info" :bordered="false" style="margin-bottom: 16px">
        设定"锁定至某日"后，该日及之前的课程记录不可修改/删除。若一键排课、清空等批量操作的范围包含已锁定日期，将整体拒绝执行（不会只改一部分），避免误改历史。
      </n-alert>
      <n-space align="center">
        <span>当前锁定至：</span>
        <n-tag :type="lockedThrough ? 'warning' : 'default'">
          {{ lockedThrough || "未锁定" }}
        </n-tag>
      </n-space>
      <n-divider />
      <n-space align="center">
        <span>锁定至：</span>
        <n-date-picker v-model:formatted-value="pick" value-format="yyyy-MM-dd" clearable />
        <n-button type="primary" @click="save">保存</n-button>
        <n-button type="error" ghost @click="clear">取消锁定</n-button>
      </n-space>
    </n-card>
  </div>
</template>
