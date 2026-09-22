import { defineStore } from "pinia"

export const useStore = defineStore("main", {
  state: () => ({
    username: "",
    userId: 0,
    isSuperuser: false,
  }),

  getters: {
    isLoggedIn: (state) => state.userId > 0,
  },

  actions: {
    logout() {
      this.username = ""
      this.userId = 0
      this.isSuperuser = false
      localStorage.removeItem("access_token")
      localStorage.removeItem("refresh_token")
    },
  },

  persist: {
    key: "timetable-auth",
    storage: localStorage,
    paths: ["username", "userId", "isSuperuser"],
  },
})
