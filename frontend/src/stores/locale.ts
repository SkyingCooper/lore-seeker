// 文件说明：
// 管理前端界面的中英文切换状态，并将选择持久化到 localStorage。
// 当前先服务首页和主布局，后续其他页面可以直接复用同一个 store。
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export type Locale = 'zh-CN' | 'en-US'

const STORAGE_KEY = 'locale'

export const useLocaleStore = defineStore('locale', () => {
  const locale = ref<Locale>((localStorage.getItem(STORAGE_KEY) as Locale) || 'zh-CN')

  const isChinese = computed(() => locale.value === 'zh-CN')

  function setLocale(value: Locale) {
    locale.value = value
    localStorage.setItem(STORAGE_KEY, value)
  }

  function toggleLocale() {
    setLocale(locale.value === 'zh-CN' ? 'en-US' : 'zh-CN')
  }

  return {
    locale,
    isChinese,
    setLocale,
    toggleLocale,
  }
})
