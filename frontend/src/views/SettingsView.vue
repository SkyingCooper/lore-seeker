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
                  <div class="text-sm font-medium text-neutral-900">{{ t.name }}</div>
                  <div class="mt-1 text-sm text-neutral-500">{{ t.target_sites?.join(', ') || copy.noSites }}</div>
                </div>
              </div>
            </div>

            <n-empty v-if="topics.length === 0" :description="copy.emptyTopics" class="rounded-xl border border-dashed border-neutral-200 py-8" />
          </div>

          <div class="mt-5 grid gap-3">
            <n-input v-model:value="newTopic.name" :placeholder="copy.topicNamePlaceholder">
              <template #prefix>
                <PenSquare :size="16" class="text-[#93a4b6]" />
              </template>
            </n-input>
            <n-input v-model:value="newTopic.description" :placeholder="copy.topicDescPlaceholder">
              <template #prefix>
                <NotebookPen :size="16" class="text-[#93a4b6]" />
              </template>
            </n-input>
            <n-input v-model:value="sitesInput" :placeholder="copy.topicSitesPlaceholder">
              <template #prefix>
                <Globe2 :size="16" class="text-[#93a4b6]" />
              </template>
            </n-input>
            <n-select v-model:value="newTopic.search_mode" :options="searchModeOptions" />
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
          <p class="mb-4 text-sm leading-6 text-neutral-500">{{ copy.preferenceHint }}</p>
          <n-input
            v-model:value="prefsText"
            type="textarea"
            :rows="14"
            :placeholder="jsonPlaceholder"
          />
          <div class="mt-4 flex justify-end">
            <n-button type="primary" @click="savePrefs">{{ copy.savePreferences }}</n-button>
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
import { useMessage, NButton, NCard, NEmpty, NGrid, NGridItem, NInput, NSelect } from 'naive-ui'
import {
  BookOpenText,
  FolderGit2,
  Globe2,
  NotebookPen,
  PenSquare,
  SlidersHorizontal,
  Sparkles,
} from '@lucide/vue'
import api from '@/api/client'
import { useLocaleStore } from '@/stores/locale'

interface TopicItem {
  id: string
  name: string
  target_sites?: string[]
}

const locale = useLocaleStore()
const message = useMessage()
const topics = ref<TopicItem[]>([])
const newTopic = ref({ name: '', description: '', search_mode: 'api', target_sites: [] as string[] })
const sitesInput = ref('')
const prefsText = ref('')
const jsonPlaceholder = '{\n  "output_lang": "zh-CN"\n}'

const copy = computed(() =>
  locale.isChinese
    ? {
        section: '设置',
        title: '设置',
        subtitle: '管理关注主题、目标站点和用户偏好，影响后续搜索计划与知识整理方式。',
        topicTitle: '关注主题',
        noSites: '未指定站点',
        emptyTopics: '还没有主题配置',
        topicNamePlaceholder: '主题名称',
        topicDescPlaceholder: '描述（可选）',
        topicSitesPlaceholder: '目标网站（逗号分隔）',
        addTopic: '添加主题',
        preferenceTitle: '个性化偏好',
        preferenceHint: '这里直接编辑 Agent 归纳出的偏好 JSON。保存前会先在前端做 JSON 解析校验。',
        savePreferences: '保存偏好',
        searchApi: 'API 搜索',
        searchCrawler: '爬虫扫描',
        searchHybrid: '混合模式',
        saveSuccess: '偏好已保存',
        saveError: 'JSON 格式错误',
      }
    : {
        section: 'Settings',
        title: 'Settings',
        subtitle: 'Manage tracked topics, target sites, and user preferences that shape future search and organization behavior.',
        topicTitle: 'Tracked Topics',
        noSites: 'No site restriction',
        emptyTopics: 'No topic configuration yet',
        topicNamePlaceholder: 'Topic name',
        topicDescPlaceholder: 'Description (optional)',
        topicSitesPlaceholder: 'Target sites (comma separated)',
        addTopic: 'Add topic',
        preferenceTitle: 'Personal Preferences',
        preferenceHint: 'Edit the JSON preferences inferred by the agent. The frontend validates the JSON before saving.',
        savePreferences: 'Save preferences',
        searchApi: 'API search',
        searchCrawler: 'Crawler',
        searchHybrid: 'Hybrid',
        saveSuccess: 'Preferences saved',
        saveError: 'Invalid JSON format',
      }
)

const searchModeOptions = computed(() => [
  { label: copy.value.searchApi, value: 'api' },
  { label: copy.value.searchCrawler, value: 'crawl' },
  { label: copy.value.searchHybrid, value: 'both' },
])

onMounted(async () => {
  const [topicsRes, meRes] = await Promise.all([
    api.get('/api/v1/search/topics'),
    api.get('/api/v1/users/me'),
  ])
  topics.value = topicsRes.data
  prefsText.value = JSON.stringify(meRes.data.preferences, null, 2)
})

async function addTopic() {
  newTopic.value.target_sites = sitesInput.value.split(',').map(s => s.trim()).filter(Boolean)
  await api.post('/api/v1/search/topics', newTopic.value)
  const res = await api.get('/api/v1/search/topics')
  topics.value = res.data
  newTopic.value = { name: '', description: '', search_mode: 'api', target_sites: [] }
  sitesInput.value = ''
}

async function savePrefs() {
  try {
    const prefs = JSON.parse(prefsText.value)
    await api.patch('/api/v1/users/me/preferences', { preferences: prefs })
    message.success(copy.value.saveSuccess)
  } catch {
    message.error(copy.value.saveError)
  }
}
</script>
