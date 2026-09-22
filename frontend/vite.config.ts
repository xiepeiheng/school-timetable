import { defineConfig, loadEnv } from "vite"
import vue from "@vitejs/plugin-vue"
import { resolve } from "path"

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "")
  return {
    // 部署在子路径时设置 VITE_BASE（如 /school-timetable/）
    base: env.VITE_BASE || "/",
    plugins: [vue()],
    resolve: {
      alias: {
        "@": resolve(__dirname, "src"),
      },
    },
    server: {
      port: 5273,
      proxy: {
        "/api": {
          target: env.VITE_DEV_PROXY || "http://127.0.0.1:8001",
          changeOrigin: true,
        },
      },
    },
  }
})
