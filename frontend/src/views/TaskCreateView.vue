<template>
  <div class="mx-auto max-w-3xl space-y-6 py-8">
    <header class="space-y-2">
      <h1 class="text-4xl font-semibold tracking-tight text-neutral-900">{{ copy.title }}</h1>
      <p class="text-sm leading-7 text-neutral-500">{{ copy.subtitle }}</p>
    </header>

    <n-card class="rounded-[28px] border-[#dfd7ca] p-6 shadow-md" :bordered="false">
      <div class="space-y-5">
        <!-- 主题选择：已有或新建 -->
        <div class="space-y-1.5">
          <label class="text-sm font-medium text-neutral-700">{{ copy.topicSource }}</label>
          <n-radio-group v-model:value="topicMode">
            <n-radio value="select">{{ copy.selectTopic }}</n-radio>
            <n-radio value="create">{{ copy.createTopic }}</n-radio>
          </n-radio-group>
        </div>

        <div v-if="topicMode === 'select'" class="space-y-1.5">
          <label class="text-sm font-medium text-neutral-700">{{ copy.topic }}</label>
          <n-select v-model:value="selectedTopicId" data-test="task-topic-select" :options="topicOptions" :placeholder="copy.topicPlaceholder" filterable />
        </div>

        <template v-else>
          <div class="space-y-1.5">
            <label class="text-sm font-medium text-neutral-700">{{ copy.topicTitle }} <span class="text-red-400">*</span></label>
            <n-input v-model:value="topicTitle" data-test="task-topic-title" :placeholder="copy.topicTitlePlaceholder" size="large" />
          </div>
          <div class="space-y-1.5">
            <label class="text-sm font-medium text-neutral-700">{{ copy.keywords }}</label>
            <n-dynamic-tags v-model:value="keywords" :placeholder="copy.keywordsPlaceholder" />
          </div>
        </template>

        <!-- 描述 -->
        <div class="space-y-1.5">
          <label class="text-sm font-medium text-neutral-700">{{ copy.description }}</label>
            <n-input v-model:value="description" data-test="task-description" type="textarea" :placeholder="copy.descriptionPlaceholder" :rows="3" size="large" />
        </div>

        <!-- 搜索方式 -->
        <div class="space-y-1.5">
          <label class="text-sm font-medium text-neutral-700">{{ copy.searchMode }}</label>
          <n-radio-group v-model:value="searchMode">
            <n-radio value="mixed">{{ copy.mixed }}</n-radio>
            <n-radio value="api">{{ copy.api }}</n-radio>
            <n-radio value="crawl">{{ copy.crawl }}</n-radio>
          </n-radio-group>
        </div>

        <!-- 搜索频率 -->
        <div class="space-y-1.5">
          <label class="text-sm font-medium text-neutral-700">{{ copy.frequency }}</label>
          <n-select v-model:value="frequency" :options="frequencyOptions" />
        </div>

        <!-- 来源网站 -->
        <div class="space-y-2">
          <label class="text-sm font-medium text-neutral-700">{{ copy.sourceSites }}</label>
          <div class="rounded-2xl border border-[#e8e0d4] bg-[#fefcf9] p-4">
            <!-- 分类级联选择 -->
            <div v-for="(sites, category) in sourceCategories" :key="category" class="mb-3 last:mb-0">
              <div class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-neutral-400">{{ category }}</div>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="site in sites"
                  :key="site"
                  class="rounded-lg border px-3 py-1 text-xs font-medium transition"
                  :class="selectedSites.includes(site) ? 'border-[#8db3d9] bg-[#eef3f8] text-[#4a6a8a]' : 'border-[#eae3d8] bg-white text-neutral-500 hover:border-[#d0c8b8]'"
                  @click="toggleSite(site)"
                >
                  {{ site }}
                </button>
              </div>
            </div>
            <!-- 自定义输入 -->
            <div class="mt-3 border-t border-[#efe8db] pt-3">
              <n-input v-model:value="customSites" data-test="task-custom-sites" size="small" :placeholder="copy.customSitesPlaceholder" />
              <p class="mt-1 text-xs text-neutral-400">{{ copy.customSitesHint }}</p>
            </div>
          </div>
        </div>

        <!-- 提交 -->
        <div class="pt-3">
          <n-button data-test="task-submit" type="primary" size="large" :loading="loading" block @click="submit">
            {{ copy.submit }}
          </n-button>
        </div>
      </div>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NCard, NDynamicTags, NInput, NRadio, NRadioGroup, NSelect, useMessage } from 'naive-ui'
import api from '@/api/client'
import { useLocaleStore } from '@/stores/locale'

const locale = useLocaleStore()
const router = useRouter()
const message = useMessage()

// 表单状态
const topicMode = ref<'select' | 'create'>('create')
const selectedTopicId = ref<number | null>(null)
const topicOptions = ref<Array<{ label: string; value: number }>>([])
const topicTitle = ref('')
const keywords = ref<string[]>([])
const description = ref('')
const searchMode = ref('mixed')
const frequency = ref('once')
const selectedSites = ref<string[]>([])
const customSites = ref('')
const loading = ref(false)

const frequencyOptions = computed(() => [
  { label: copy.value.once, value: 'once' },
  { label: copy.value.daily, value: 'daily' },
  { label: copy.value.weekly, value: 'weekly' },
  { label: copy.value.biweekly, value: 'biweekly' },
  { label: copy.value.monthly, value: 'monthly' },
])

const sourceCategories: Record<string, string[]> = {
  代码托管: ['GitHub', 'GitLab', 'Gitee', 'Bitbucket', 'SourceForge', 'GitCode', 'Coding.net'],
  技术社区: ['Stack Overflow', 'Reddit', 'Hacker News', 'Dev.to', '知乎', '掘金', 'SegmentFault', 'CSDN'],
  学术论文: ['arXiv', 'PubMed', 'Google Scholar', 'IEEE Xplore', 'ACM DL', 'Semantic Scholar', '知网'],
  开源基金会: ['Apache Projects', 'Linux Foundation', 'CNCF', 'Python.org', 'Rust社区', 'Eclipse Foundation', 'OpenJS Foundation'],
  新闻资讯: ['TechCrunch', 'V2EX', 'Product Hunt', 'HackerNoon', '36氪', '少数派', 'The Verge'],
}

function toggleSite(site: string) {
  const idx = selectedSites.value.indexOf(site)
  if (idx >= 0) {
    selectedSites.value.splice(idx, 1)
  } else if (selectedSites.value.length < 5) {
    selectedSites.value.push(site)
  } else {
    message.warning(copy.value.maxSites)
  }
}

onMounted(async () => {
  try {
    const res = await api.get('/api/v1/search/topics')
    topicOptions.value = res.data.map((t: any) => ({ label: t.title, value: Number(t.id) }))
  } catch { /* ignore */ }
})

async function submit() {
  if (topicMode.value === 'create' && !topicTitle.value.trim()) {
    message.warning(copy.value.topicRequired)
    return
  }
  if (topicMode.value === 'select' && !selectedTopicId.value) {
    message.warning(copy.value.topicSelectRequired)
    return
  }

  loading.value = true
  try {
    const sites = [...selectedSites.value]
    if (customSites.value.trim()) {
      sites.push(...customSites.value.split(';').map(s => s.trim()).filter(Boolean))
    }

    const res = await api.post('/api/v1/tasks', {
      topic_id: topicMode.value === 'select' ? selectedTopicId.value : null,
      topic_title: topicMode.value === 'create' ? topicTitle.value : null,
      topic_keywords: keywords.value,
      topic_description: description.value || null,
      source_sites: sites.slice(0, 5),
      search_mode: searchMode.value,
      frequency: frequency.value,
    })
    message.success(copy.value.createSuccess)
    router.push(`/tasks/${res.data.id}`)
  } catch (e: any) {
    message.error(e.response?.data?.detail?.detail || copy.value.createFailed)
  } finally {
    loading.value = false
  }
}

const copy = computed(() =>
  locale.isChinese
    ? {
        title: '新建任务',
        subtitle: '设置搜索主题、关键词、来源和目标，创建自动化知识收集任务。',
        topicSource: '主题来源',
        selectTopic: '选择已有主题',
        createTopic: '创建新主题',
        topic: '已有主题',
        topicPlaceholder: '搜索并选择主题...',
        topicTitle: '主题名称',
        topicTitlePlaceholder: '如：Rust 异步编程最佳实践',
        keywords: '关键词',
        keywordsPlaceholder: '输入后回车添加，如 AI、大模型',
        description: '描述',
        descriptionPlaceholder: '关于搜索主题的说明，如：关注技术实现、行业应用等',
        searchMode: '搜索方式',
        api: 'API 搜索',
        crawl: '爬虫',
        mixed: '混合',
        frequency: '搜索频率',
        once: '仅一次',
        daily: '每天',
        weekly: '每周',
        biweekly: '每两周',
        monthly: '每月',
        sourceSites: '来源网站（可选，最多5个）',
        customSitesPlaceholder: '自定义网址，分号隔开',
        customSitesHint: '如 https://example.com; https://blog.example.com',
        submit: '创建任务',
        topicRequired: '请输入主题名称',
        topicSelectRequired: '请选择一个已有主题',
        maxSites: '最多选择5个来源网站',
        createSuccess: '任务创建成功',
        createFailed: '创建失败，请重试',
      }
    : {
        title: 'New Task',
        subtitle: 'Set up an automated knowledge collection task with topic, keywords, and sources.',
        topicSource: 'Topic source',
        selectTopic: 'Select existing',
        createTopic: 'Create new',
        topic: 'Existing topic',
        topicPlaceholder: 'Search and select a topic...',
        topicTitle: 'Topic title',
        topicTitlePlaceholder: 'e.g. Rust async programming best practices',
        keywords: 'Keywords',
        keywordsPlaceholder: 'Type and press Enter, e.g. AI, LLM',
        description: 'Description',
        descriptionPlaceholder: 'What this topic is about: technology, business, market trends, etc.',
        searchMode: 'Search mode',
        api: 'API Search',
        crawl: 'Crawler',
        mixed: 'Mixed',
        frequency: 'Frequency',
        once: 'Once',
        daily: 'Daily',
        weekly: 'Weekly',
        biweekly: 'Bi-weekly',
        monthly: 'Monthly',
        sourceSites: 'Source sites (optional, max 5)',
        customSitesPlaceholder: 'Custom URLs, separated by semicolons',
        customSitesHint: 'e.g. https://example.com; https://blog.example.com',
        submit: 'Create Task',
        topicRequired: 'Topic title is required',
        topicSelectRequired: 'Please select an existing topic',
        maxSites: 'Maximum 5 sites allowed',
        createSuccess: 'Task created successfully',
        createFailed: 'Failed to create task',
      }
)
</script>
