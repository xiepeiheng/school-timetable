export interface LoginReq {
  username: string
  password: string
}

export interface LoginRes {
  access: string
  refresh: string
  user_id: number
  username: string
  is_superuser: boolean
}

export interface MeRes {
  user_id: number
  username: string
  is_superuser: boolean
}
