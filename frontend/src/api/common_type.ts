export interface ResponseData<T> {
  success: boolean
  code: number
  message: string
  data: T
}

export interface PaginatedData<T> {
  total: number
  page: number
  size: number
  items: T[]
}
