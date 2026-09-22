import dayjs from "dayjs"
import isoWeek from "dayjs/plugin/isoWeek"

dayjs.extend(isoWeek)

export const WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

export function fmt(d: Date | string | number): string {
  return dayjs(d).format("YYYY-MM-DD")
}

/** 返回 date 所在周的周一 */
export function getMonday(d: Date | string | number): string {
  const day = dayjs(d)
  const isoWeekday = day.isoWeekday()
  return day.subtract(isoWeekday - 1, "day").format("YYYY-MM-DD")
}

export function addDays(d: string, n: number): string {
  return dayjs(d).add(n, "day").format("YYYY-MM-DD")
}

/** 由周一日期得到整周 7 天日期数组 */
export function weekDates(monday: string): string[] {
  return Array.from({ length: 7 }, (_, i) => addDays(monday, i))
}

export function weekdayIndex(d: string): number {
  return dayjs(d).isoWeekday() // 1..7
}
