<script setup lang="ts">
import { useRouter } from "vue-router"
const router = useRouter()
</script>

<template>
  <n-result status="404" title="页面不存在" description="请检查地址是否正确">
    <template #footer>
      <n-button @click="router.push({ name: 'schedule' })">返回首页</n-button>
    </template>
  </n-result>
</template>
