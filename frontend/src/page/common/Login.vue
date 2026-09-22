<script setup lang="ts">
import { ref } from "vue"
import { useRouter } from "vue-router"
import { useMessage } from "naive-ui"
import { reqLogin } from "@/api/auth"
import { useStore } from "@/store"

const router = useRouter()
const message = useMessage()
const store = useStore()

const form = ref({ username: "", password: "" })
const loading = ref(false)

async function onSubmit() {
  if (!form.value.username || !form.value.password) {
    message.warning("请输入用户名和密码")
    return
  }
  loading.value = true
  try {
    const res = await reqLogin(form.value)
    localStorage.setItem("access_token", res.data.access)
    localStorage.setItem("refresh_token", res.data.refresh)
    store.username = res.data.username
    store.userId = res.data.user_id
    store.isSuperuser = res.data.is_superuser
    message.success("登录成功")
    router.push({ name: "schedule" })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div
    style="
      height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    "
  >
    <n-card title="高一（1）部排课系统" style="width: 360px">
      <n-form>
        <n-form-item label="用户名">
          <n-input v-model:value="form.username" placeholder="用户名" />
        </n-form-item>
        <n-form-item label="密码">
          <n-input
            v-model:value="form.password"
            type="password"
            placeholder="密码"
            @keyup.enter="onSubmit"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-button type="primary" block :loading="loading" @click="onSubmit">
          登录
        </n-button>
      </template>
    </n-card>
  </div>
</template>
