<script setup lang="ts">
import { computed, h, ref } from "vue"
import { RouterLink, useRoute, useRouter } from "vue-router"
import { NIcon, type MenuOption } from "naive-ui"
import {
  BarChartOutline,
  BookOutline,
  CalendarNumberOutline,
  CalendarOutline,
  CopyOutline,
  DocumentTextOutline,
  EyeOutline,
  FolderOutline,
  LinkOutline,
  ListOutline,
  LockClosedOutline,
  MenuOutline,
  PeopleOutline,
  PersonOutline,
  SchoolOutline,
  SettingsOutline,
  StatsChartOutline,
  TimeOutline,
} from "@vicons/ionicons5"
import { useStore } from "@/store"

const route = useRoute()
const router = useRouter()
const store = useStore()

function renderIcon(icon: unknown) {
  return () => h(NIcon, null, { default: () => h(icon as never) })
}

function link(name: string, label: string, icon: unknown): MenuOption {
  return {
    key: name,
    label: () => h(RouterLink, { to: { name } }, { default: () => label }),
    icon: renderIcon(icon),
  }
}

const menuOptions: MenuOption[] = [
  link("schedule", "排课", CalendarOutline),
  link("templates", "模板管理", CopyOutline),
  {
    key: "view",
    label: "查看",
    icon: renderIcon(EyeOutline),
    children: [
      link("class-timetable", "班级课表", ListOutline),
      link("teacher-timetable", "教师课表", PersonOutline),
    ],
  },
  {
    key: "report",
    label: "报表",
    icon: renderIcon(BarChartOutline),
    children: [
      link("teacher-detail", "教师课时明细", DocumentTextOutline),
      link("teacher-summary", "教师课时汇总", StatsChartOutline),
    ],
  },
  {
    key: "base",
    label: "基础资料",
    icon: renderIcon(FolderOutline),
    children: [
      link("base-subjects", "学科", BookOutline),
      link("base-teachers", "教师", PeopleOutline),
      link("base-classes", "班级", SchoolOutline),
      link("base-time-slots", "时间段", TimeOutline),
      link("base-semesters", "学期", CalendarNumberOutline),
      link("base-assignments", "任课关系", LinkOutline),
    ],
  },
  {
    key: "settings",
    label: "设置",
    icon: renderIcon(SettingsOutline),
    children: [link("settings-lock", "锁定设置", LockClosedOutline)],
  },
]

const collapsed = ref(window.innerWidth < 1024)
const activeKey = computed(() => route.name as string)

function onLogout() {
  store.logout()
  router.push({ name: "login" })
}
</script>

<template>
  <n-layout has-sider style="height: 100vh">
    <n-layout-sider
      bordered
      collapsible
      collapse-mode="width"
      :width="220"
      :collapsed-width="64"
      :collapsed="collapsed"
      :show-trigger="false"
      content-style="padding-top: 12px"
      @update:collapsed="(v: boolean) => (collapsed = v)"
    >
      <div
        style="
          padding: 0 16px 12px;
          font-weight: 700;
          font-size: 16px;
          white-space: nowrap;
          overflow: hidden;
        "
      >
        {{ collapsed ? "排课" : "高一（1）部排课" }}
      </div>
      <n-menu
        :value="activeKey"
        :options="menuOptions"
        :collapsed="collapsed"
        :collapsed-width="64"
        :collapsed-icon-size="20"
      />
    </n-layout-sider>
    <n-layout>
      <n-layout-header
        bordered
        style="
          height: 52px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 16px;
          gap: 12px;
        "
      >
        <n-button quaternary size="small" @click="collapsed = !collapsed">
          <template #icon>
            <n-icon><MenuOutline /></n-icon>
          </template>
        </n-button>
        <div style="display: flex; align-items: center; gap: 12px">
          <span>{{ store.username }}</span>
          <n-button size="small" @click="onLogout">退出</n-button>
        </div>
      </n-layout-header>
      <n-layout-content
        content-style="padding: 16px; height: calc(100vh - 52px); overflow: auto"
      >
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>
