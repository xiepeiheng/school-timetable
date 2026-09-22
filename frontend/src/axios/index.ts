import axios, {
  AxiosInstance,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from "axios"
import { createDiscreteApi } from "naive-ui"

/** 响应拦截器已解包信封，因此对外暴露的返回类型即 request<T> 的 T。 */
export interface ApiClient {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
  patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>
  defaults: AxiosInstance["defaults"]
}

const { message } = createDiscreteApi(["message"])

const TOKEN_KEY = "access_token"
const REFRESH_TOKEN_KEY = "refresh_token"

const http: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
})

http.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    if (config.data instanceof FormData) {
      delete config.headers?.["Content-Type"]
    }
    return config
  },
  (error) => Promise.reject(error),
)

let refreshPromise: Promise<boolean> | null = null

// 并发刷新锁：多个 401 只触发一次刷新
async function refreshToken(): Promise<boolean> {
  if (refreshPromise) return refreshPromise

  const refreshTokenStr = localStorage.getItem(REFRESH_TOKEN_KEY)
  if (!refreshTokenStr) return false

  refreshPromise = axios
    .post(`${http.defaults.baseURL}/auth/refresh/`, {
      refresh: refreshTokenStr,
    })
    .then((res) => {
      const { access } = res.data.data
      localStorage.setItem(TOKEN_KEY, access)
      return true
    })
    .catch(() => {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(REFRESH_TOKEN_KEY)
      window.location.href = "/login"
      return false
    })
    .finally(() => {
      refreshPromise = null
    })

  return refreshPromise
}

http.interceptors.response.use(
  (response) => {
    if (response.status === 204) {
      return { success: true, code: 200, message: "操作成功", data: null }
    }
    return response.data
  },
  async (error) => {
    if (error.response) {
      const { status, data } = error.response

      if (status === 401) {
        const refreshed = await refreshToken()
        if (refreshed && error.config) {
          const token = localStorage.getItem(TOKEN_KEY)
          error.config.headers!.Authorization = `Bearer ${token}`
          return http(error.config)
        }
        return Promise.reject(error)
      }

      const msgMap: Record<number, string> = {
        403: "没有操作权限",
        404: "资源不存在",
        500: "服务器内部错误",
      }
      message.error(data?.message || msgMap[status] || "请求失败")
    } else if (error.request) {
      message.error("网络连接失败")
    } else {
      message.error("请求配置错误")
    }

    return Promise.reject(error)
  },
)

export default http as unknown as ApiClient
