import http from "@/axios"
import type { ResponseData } from "@/api/common_type"
import type { LoginReq, LoginRes, MeRes } from "./type"

export const reqLogin = (data: LoginReq) =>
  http.post<ResponseData<LoginRes>>("/auth/login/", data)

export const reqMe = () => http.get<ResponseData<MeRes>>("/auth/me/")
