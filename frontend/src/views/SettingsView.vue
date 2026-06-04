<template>
  <div class="space-y-6">
    <header class="space-y-2">
      <div class="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-neutral-400">
        <SlidersHorizontal :size="14" class="text-[#8ca0b5]" />
        <span>{{ copy.section }}</span>
      </div>
      <h1 class="text-3xl font-semibold tracking-tight text-neutral-900">{{ copy.title }}</h1>
      <p class="max-w-2xl text-sm leading-6 text-neutral-500">{{ copy.subtitle }}</p>
    </header>

    <n-grid cols="1 l:2" :x-gap="16" :y-gap="16" responsive="screen">
      <n-grid-item>
        <n-card :bordered="false" class="h-full rounded-[28px] border border-[#dfd7ca] shadow-[0_18px_48px_rgba(148,131,105,0.08)]">
          <template #header>
            <div class="flex items-center gap-3">
              <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#f7efe5] text-[#6f8cab]">
                <FolderGit2 :size="18" />
              </div>
              <div class="text-2xl font-semibold text-neutral-900">{{ copy.topicTitle }}</div>
            </div>
          </template>
          <div class="space-y-3">
            <div
              v-for="t in topics"
              :key="t.id"
              class="rounded-2xl border border-[#e4ddcf] bg-[#fcf8f1] px-4 py-3"
            >
              <div class="flex items-center gap-3">
                <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-white text-[#89a1ba]">
                  <BookOpenText :size="16" />
                </div>
                <div>
                  <div class="text-sm font-medium text-neutral-900">{{ t.title }}</div>
                  <div class="mt-1 text-sm text-neutral-500">{{ t.keywords?.join(', ') || t.description || copy.noKeywords }}</div>
                </div>
              </div>
            </div>

            <n-empty v-if="topics.length === 0" :description="copy.emptyTopics" class="rounded-xl border border-dashed border-neutral-200 py-8" />
          </div>

          <div class="mt-5 grid gap-3">
            <n-input v-model:value="newTopic.title" :placeholder="copy.topicNamePlaceholder">
              <template #prefix>
                <PenSquare :size="16" class="text-[#93a4b6]" />
              </template>
            </n-input>
            <n-input v-model:value="newTopic.description" :placeholder="copy.topicDescPlaceholder">
              <template #prefix>
                <NotebookPen :size="16" class="text-[#93a4b6]" />
              </template>
            </n-input>
            <n-dynamic-tags v-model:value="newTopic.keywords" :placeholder="copy.topicKeywordsPlaceholder" />
            <n-button type="primary" @click="addTopic">{{ copy.addTopic }}</n-button>
          </div>
        </n-card>
      </n-grid-item>

      <n-grid-item>
        <n-card :bordered="false" class="h-full rounded-[28px] border border-[#dfd7ca] shadow-[0_18px_48px_rgba(148,131,105,0.08)]">
          <template #header>
            <div class="flex items-center gap-3">
              <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#edf2f7] text-[#6c86a2]">
                <Sparkles :size="18" />
              </div>
              <div class="text-2xl font-semibold text-neutral-900">{{ copy.preferenceTitle }}</div>
            </div>
          </template>
          <template v-if="auth.isGuest">
            <div class="rounded-2xl border border-dashed border-[#e4ddcf] bg-[#fcf8f1] px-4 py-8 text-center text-sm text-neutral-500">
              {{ copy.guestHint }}
            </div>
          </template>
          <template v-else>
            <p class="mb-4 text-sm leading-6 text-neutral-500">{{ copy.preferenceHint }}</p>
            <n-input
              v-model:value="prefsText"
              type="textarea"
              :rows="10"
              :placeholder="jsonPlaceholder"
            />
            <div class="mt-4 flex flex-wrap justify-end gap-3">
              <n-button secondary @click="loadPreferences">{{ copy.reloadPreferences }}</n-button>
              <n-button secondary @click="clearPreferences">{{ copy.clearPreferences }}</n-button>
              <n-button type="primary" @click="savePrefs">{{ copy.savePreferences }}</n-button>
            </div>

            <div class="mt-6 space-y-3">
              <div class="text-sm font-semibold text-neutral-800">{{ copy.preferenceList }}</div>
              <div v-if="preferenceItems.length === 0" class="rounded-2xl border border-dashed border-[#e4ddcf] py-8 text-center text-sm text-neutral-400">
                {{ copy.emptyPreferences }}
              </div>
              <div v-for="item in preferenceItems" :key="item.key" class="rounded-2xl border border-[#e4ddcf] bg-[#fcf8f1] px-4 py-3">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <div class="font-medium text-neutral-900">{{ item.key }}</div>
                    <div class="mt-1 text-xs text-neutral-400">{{ item.category }} · {{ item.updated_at || '-' }}</div>
                    <pre class="mt-2 overflow-x-auto whitespace-pre-wrap rounded-xl bg-white/75 px-3 py-2 text-xs text-neutral-600">{{ stringifyPreference(item.value) }}</pre>
                  </div>
                  <n-button text type="error" @click="deletePreference(item.key)">{{ copy.deletePreference }}</n-button>
                </div>
              </div>
            </div>
          </template>
          <div class="mt-6 rounded-2xl border border-[#e4ddcf] bg-[#fcf8f1] px-4 py-4">
            <div class="text-sm font-semibold text-neutral-800">{{ copy.singlePreferenceTitle }}</div>
            <div class="mt-3 grid gap-3">
              <n-input v-model:value="draftKey" :placeholder="copy.preferenceKeyPlaceholder" />
              <n-input v-model:value="draftValue" type="textarea" :rows="4" :placeholder="copy.preferenceValuePlaceholder" />
              <div class="flex justify-end">
                <n-button type="primary" :disabled="auth.isGuest" @click="saveSinglePreference">{{ copy.saveSinglePreference }}</n-button>
              </div>
            </div>
          </div>
        </n-card>
      </n-grid-item>
    </n-grid>
  </div>
</template>

<script setup lang="ts">
// 文件说明：
// SettingsView 用于管理主题配置和用户偏好，是搜索计划与知识整理行为的前端配置入口。
import { computed, onMounted, ref } from 'vue'
import { useMessage, NButton, NCard, NDynamicTags, NEmpty, NGrid, NGridItem, NInput } from 'naive-ui'
import {
  BookOpenText,
  FolderGit2,
  NotebookPen,
  PenSquare,
  SlidersHorizontal,
  Sparkles,
} from '@lucide/vue'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useLocaleStore } from '@/stores/locale'

interface TopicItem {
  id: string
  title: string
  description?: string | null
  keywords?: string[]
}

interface TopicForm {
  title: string
  description: string
  keywords: string[]
}

const locale = useLocaleStore()
const auth = useAuthStore()
const message = useMessage()
const topics = ref<TopicItem[]>([])
const preferenceItems = ref<Array<{ key: string; value: unknown; category: string; updated_at?: string | null }>>([])
const newTopic = ref<TopicForm>({
  title: '',
  description: '',
  keywords: [],
})
const prefsText = ref('')
const draftKey = ref('')
const draftValue = ref('')
const jsonPlaceholder = '{\n  "output_lang": "zh-CN"\n}'

const copy = computed(() =>
  locale.isChinese
    ? {
        section: '设置',
        title: '设置',
        subtitle: '管理关注主题、目标站点和用户偏好，影响后续搜索计划与知识整理方式。',
        topicTitle: '关注主题',
        noKeywords: '未设置关键词',
        emptyTopics: '还没有主题配置',
        topicNamePlaceholder: '主题名称',
        topicDescPlaceholder: '描述（可选）',
        topicKeywordsPlaceholder: '添加关键词',
        addTopic: '添加主题',
        preferenceTitle: '个性化偏好',
        preferenceHint: '这里直接编辑 Agent 归纳出的偏好 JSON。保存前会先在前端做 JSON 解析校验。',
        guestHint: '游客状态下无法写入长期偏好，注册登录后即可管理。',
        reloadPreferences: '重新加载',
        clearPreferences: '清空偏好',
        preferenceList: '当前偏好项',
        emptyPreferences: '还没有偏好项',
        deletePreference: '删除',
        singlePreferenceTitle: '单项偏好维护',
        preferenceKeyPlaceholder: '偏好键，如 output_lang',
        preferenceValuePlaceholder: '偏好值 JSON，如 \"zh-CN\" 或 {\"tone\":\"concise\"}',
        saveSinglePreference: '保存单项偏好',
        savePreferences: '保存偏好',
        topicRequired: '请输入主题名称',
        addSuccess: '主题已添加',
        saveSuccess: '偏好已保存',
        saveError: 'JSON 格式错误',
        clearSuccess: '偏好已清空',
        deleteSuccess: '偏好已删除',
        singleSaveSuccess: '单项偏好已保存',
        keyRequired: '请输入偏好键',
      }
    : {
        section: 'Settings',
        title: 'Settings',
        subtitle: 'Manage tracked topics, target sites, and user preferences that shape future search and organization behavior.',
        topicTitle: 'Tracked Topics',
        noKeywords: 'No keywords',
        emptyTopics: 'No topic configuration yet',
        topicNamePlaceholder: 'Topic name',
        topicDescPlaceholder: 'Description (optional)',
        topicKeywordsPlaceholder: 'Add keywords',
        addTopic: 'Add topic',
        preferenceTitle: 'Personal Preferences',
        preferenceHint: 'Edit the JSON preferences inferred by the agent. The frontend validates the JSON before saving.',
        guestHint: 'Guests cannot persist long-term preferences. Sign in to manage them.',
        reloadPreferences: 'Reload',
        clearPreferences: 'Clear preferences',
        preferenceList: 'Current preference items',
        emptyPreferences: 'No preferences yet',
        deletePreference: 'Delete',
        singlePreferenceTitle: 'Single preference editor',
        preferenceKeyPlaceholder: 'Preference key, e.g. output_lang',
        preferenceValuePlaceholder: 'JSON value, e.g. \"en-US\" or {\"tone\":\"concise\"}',
        saveSinglePreference: 'Save single preference',
        savePreferences: 'Save preferences',
        topicRequired: 'Topic name is required',
        addSuccess: 'Topic added',
        saveSuccess: 'Preferences saved',
        saveError: 'Invalid JSON format',
        clearSuccess: 'Preferences cleared',
        deleteSuccess: 'Preference deleted',
        singleSaveSuccess: 'Preference saved',
        keyRequired: 'Preference key is required',
      }
)

onMounted(async () => {
  const [topicsRes, meRes] = await Promise.all([
    api.get('/api/v1/search/topics'),
    api.get('/api/v1/users/me'),
  ])
  topics.value = topicsRes.data
  prefsText.value = JSON.stringify(meRes.data.preferences, null, 2)
  if (!auth.isGuest) {
    await loadPreferences()
  }
})

async function addTopic() {
  if (!newTopic.value.title.trim()) {
    message.warning(copy.value.topicRequired)
    return
  }
  await api.post('/api/v1/search/topics', newTopic.value)
  const res = await api.get('/api/v1/search/topics')
  topics.value = res.data
  newTopic.value = { title: '', description: '', keywords: [] }
  message.success(copy.value.addSuccess)
}

async function savePrefs() {
  try {
    const prefs = JSON.parse(prefsText.value)
    await api.patch('/api/v1/users/me/preferences', { preferences: prefs })
    await loadPreferences()
    message.success(copy.value.saveSuccess)
  } catch {
    message.error(copy.value.saveError)
  }
}

async function loadPreferences() {
  const res = await api.get('/api/v1/users/me/preferences')
  preferenceItems.value = res.data.items || []
}

async function deletePreference(key: string) {
  await api.delete(`/api/v1/users/me/preferences/${encodeURIComponent(key)}`)
  await loadPreferences()
  const all = Object.fromEntries(preferenceItems.value.map((item) => [item.key, item.value]))
  prefsText.value = JSON.stringify(all, null, 2)
  message.success(copy.value.deleteSuccess)
}

async function clearPreferences() {
  await api.delete('/api/v1/users/me/preferences')
  preferenceItems.value = []
  prefsText.value = '{}'
  message.success(copy.value.clearSuccess)
}

async function saveSinglePreference() {
  if (!draftKey.value.trim()) {
    message.warning(copy.value.keyRequired)
    return
  }
  try {
    const parsed = JSON.parse(draftValue.value)
    await api.put(`/api/v1/users/me/preferences/${encodeURIComponent(draftKey.value.trim())}`, {
      value: parsed,
    })
    draftKey.value = ''
    draftValue.value = ''
    await loadPreferences()
    const all = Object.fromEntries(preferenceItems.value.map((item) => [item.key, item.value]))
    prefsText.value = JSON.stringify(all, null, 2)
    message.success(copy.value.singleSaveSuccess)
  } catch {
    message.error(copy.value.saveError)
  }
}

function stringifyPreference(value: unknown) {
  return JSON.stringify(value, null, 2)
}
</script>
