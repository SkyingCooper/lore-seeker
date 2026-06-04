<template>
  <div class="space-y-6">
    <header class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div class="space-y-2">
        <div class="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-neutral-400">
          <LibraryBig :size="14" class="text-[#8ca0b5]" />
          <span>{{ copy.sectionLabel }}</span>
        </div>
        <h1 class="text-4xl font-semibold tracking-tight text-neutral-900">{{ copy.title }}</h1>
        <p class="max-w-2xl text-sm leading-7 text-neutral-500">{{ copy.subtitle }}</p>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <n-input
          v-model:value="query"
          class="w-full min-w-[240px] lg:w-80"
          size="large"
          :placeholder="copy.queryPlaceholder"
          @keyup.enter="startSearch"
        >
          <template #prefix>
            <Search :size="16" class="text-[#93a4b6]" />
          </template>
        </n-input>
        <n-button type="primary" size="large" :loading="searching" @click="startSearch">
          <template #icon>
            <Plus :size="18" />
          </template>
          {{ copy.newPage }}
        </n-button>
      </div>
    </header>

    <section class="rounded-[28px] border border-[#dfd7ca] bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(255,251,245,0.96))] px-5 py-5 shadow-[0_18px_48px_rgba(148,131,105,0.08)]">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div class="flex flex-wrap items-center gap-2">
          <button
            v-for="view in viewTabs"
            :key="view.key"
            class="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm transition"
            :class="activeTab === view.key ? 'bg-[#fff7ed] font-medium text-[#334e6b] shadow-[0_10px_24px_rgba(120,136,157,0.14)]' : 'text-neutral-500 hover:bg-white/80'"
            @click="activeTab = view.key"
          >
            <component :is="view.icon" :size="15" />
            {{ view.label }}
          </button>
        </div>

        <div class="flex flex-wrap items-center gap-3 text-sm text-neutral-500">
          <n-select v-model:value="searchMode" class="min-w-[160px]" :options="searchModeOptions" />
          <n-button tertiary circle @click="cycleStatusFilter">
            <template #icon>
              <Funnel :size="17" />
            </template>
          </n-button>
          <n-button tertiary circle @click="startSearch">
            <template #icon>
              <Search :size="17" />
            </template>
          </n-button>
          <n-button tertiary circle @click="toggleSummaryMode">
            <template #icon>
              <SlidersHorizontal :size="17" />
            </template>
          </n-button>
        </div>
      </div>

      <n-alert v-if="taskId" type="info" class="mt-4 rounded-2xl border border-[#dfd7ca]">
        {{ copy.taskStatus(taskId.slice(0, 8), taskStatus) }}
      </n-alert>

      <div class="mt-5 overflow-hidden rounded-[24px] border border-[#e2dacd] bg-white/80">
        <div class="grid grid-cols-[minmax(260px,1.3fr)_160px_170px_170px] border-b border-[#e7dfd3] bg-[#fbf5ec] px-4 py-3 text-xs font-medium uppercase tracking-[0.14em] text-neutral-400">
          <div class="flex items-center gap-2">
            <FileText :size="14" />
            <span>{{ copy.columnTitle }}</span>
          </div>
          <div class="flex items-center gap-2">
            <CircleUserRound :size="14" />
            <span>{{ copy.columnOwner }}</span>
          </div>
          <div class="flex items-center gap-2">
            <BadgeInfo :size="14" />
            <span>{{ copy.columnSource }}</span>
          </div>
          <div class="flex items-center gap-2">
            <Clock3 :size="14" />
            <span>{{ copy.columnUpdated }}</span>
          </div>
        </div>

        <div v-if="filteredReports.length === 0" class="bg-white px-6 py-14">
          <n-empty :description="copy.empty" />
        </div>

        <button
          v-for="report in filteredReports"
          :key="report.id"
          class="grid w-full grid-cols-[minmax(260px,1.3fr)_160px_170px_170px] items-center border-b border-[#ece4d9] bg-white/90 px-4 py-4 text-left transition last:border-b-0 hover:bg-[#fffaf2]"
          @click="router.push(`/browse/${report.id}`)"
        >
          <div class="flex min-w-0 items-center gap-3 pr-4">
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[#f6efe6] text-[#7d9ab7]">
              <FilePenLine :size="18" />
            </div>
            <div class="min-w-0">
              <div class="truncate text-[15px] font-medium text-neutral-900">{{ report.title || `${copy.reportNo} #${report.id}` }}</div>
              <div class="mt-1 text-sm text-neutral-500" :class="compactSummary ? 'truncate' : 'line-clamp-2'">
                {{ report.summary || copy.emptySummary }}
              </div>
            </div>
          </div>
          <div class="text-sm text-neutral-600">{{ ownerLabel }}</div>
          <div class="text-sm text-neutral-600">{{ reportSource(report) }}</div>
          <div class="text-sm text-neutral-500">{{ formatDate(report.created_at) }}</div>
        </button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
// 文件说明：
// BrowseView 作为首页工作区，承担“发起搜索 + 查看近期报告”两个核心职责。
// 这里的结构参考 Notion 的数据库工作页，但保留 Lore Seeker 自己的动作语义和视觉标识。
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NAlert, NButton, NEmpty, NInput, NSelect, useMessage } from 'naive-ui'
import {
  BadgeInfo,
  CircleUserRound,
  Clock3,
  FilePenLine,
  FileText,
  Funnel,
  LibraryBig,
  Lock,
  Plus,
  Search,
  SlidersHorizontal,
  Sparkles,
  Star,
  Users,
} from '@lucide/vue'
import api from '@/api/client'
import { useLocaleStore } from '@/stores/locale'

interface ReportListItem {
  id: string
  title: string
  summary: string | null
  created_at?: string
  quality_score?: number | null
  status?: string
  user_satisfaction?: string | null
}

const locale = useLocaleStore()
const router = useRouter()
const message = useMessage()

const query = ref('')
const searchMode = ref('mixed')
const searching = ref(false)
const taskId = ref<string | null>(null)
const taskStatus = ref('')
const activeTab = ref('recent')
const statusFilter = ref<'all' | 'completed' | 'failed'>('all')
const compactSummary = ref(false)
const reports = ref<ReportListItem[]>([])

const copy = computed(() =>
  locale.isChinese
    ? {
        sectionLabel: '工作区',
        title: '首页',
        subtitle: '像一个研究数据库一样查看最近的报告、管理搜索入口，并持续沉淀长期知识资产。',
        queryPlaceholder: '输入新的搜索主题...',
        newPage: '新页面',
        filter: '筛选',
        search: '搜索',
        display: '显示',
        columnTitle: '页面名称',
        columnOwner: '创建者',
        columnSource: '来源',
        columnUpdated: '上次编辑时间',
        empty: '当前筛选条件下还没有报告。',
        emptySummary: '暂无摘要',
        recent: '全部',
        favorites: '高质量',
        shared: '已好评',
        privateTab: '待改进',
        reportSource: '知识报告',
        reportNo: '报告',
        owner: '你',
        taskStatus: (id: string, status: string) => `任务 ${id}... 状态：${status}`,
        filterAll: '已切换为全部状态',
        filterCompleted: '已切换为成功报告',
        filterFailed: '已切换为失败报告',
        displayCompact: '已切换为紧凑摘要',
        displayFull: '已切换为完整摘要',
      }
    : {
        sectionLabel: 'Workspace',
        title: 'Home',
        subtitle: 'Review recent reports like a research library, launch new searches, and keep long-lived knowledge assets in one place.',
        queryPlaceholder: 'Type a new research topic...',
        newPage: 'New page',
        filter: 'Filter',
        search: 'Search',
        display: 'Display',
        columnTitle: 'Page',
        columnOwner: 'Owner',
        columnSource: 'Source',
        columnUpdated: 'Last edited',
        empty: 'No reports match the current filters.',
        emptySummary: 'No summary yet',
        recent: 'All',
        favorites: 'High quality',
        shared: 'Well rated',
        privateTab: 'Needs review',
        reportSource: 'Knowledge report',
        reportNo: 'Report',
        owner: 'You',
        taskStatus: (id: string, status: string) => `Task ${id}... status: ${status}`,
        filterAll: 'Showing all statuses',
        filterCompleted: 'Showing completed reports only',
        filterFailed: 'Showing failed reports only',
        displayCompact: 'Switched to compact summaries',
        displayFull: 'Switched to full summaries',
      }
)

const viewTabs = computed(() => [
  { key: 'recent', label: copy.value.recent, icon: Clock3 },
  { key: 'favorites', label: copy.value.favorites, icon: Star },
  { key: 'shared', label: copy.value.shared, icon: Users },
  { key: 'private', label: copy.value.privateTab, icon: Lock },
])

const searchModeOptions = computed(() => [
  { label: locale.isChinese ? '混合模式' : 'Hybrid', value: 'mixed' },
  { label: locale.isChinese ? 'API 搜索' : 'API search', value: 'api' },
  { label: locale.isChinese ? '爬虫扫描' : 'Crawler', value: 'crawl' },
])

const ownerLabel = computed(() => copy.value.owner)
const filteredReports = computed(() =>
  reports.value.filter((report) => {
    if (statusFilter.value === 'completed' && report.status !== 'completed' && report.status !== 'success') return false
    if (statusFilter.value === 'failed' && report.status !== 'failed') return false
    if (activeTab.value === 'favorites') return (report.quality_score ?? 0) >= 80
    if (activeTab.value === 'shared') return report.user_satisfaction === 'satisfied'
    if (activeTab.value === 'private') return (report.quality_score ?? 0) < 80 || report.user_satisfaction === 'dissatisfied'
    return true
  })
)

onMounted(loadReports)

async function loadReports() {
  const res = await api.get('/api/v1/reports/')
  reports.value = res.data
}

async function startSearch() {
  if (!query.value.trim()) return
  searching.value = true
  try {
    const res = await api.post('/api/v1/search/start', {
      query: query.value,
      search_mode: searchMode.value,
    })
    taskId.value = res.data.task_id
    taskStatus.value = 'pending'
    // 当前仍然使用轮询获取异步任务结果，后续可以切到 WebSocket/SSE。
    pollTask(res.data.task_id)
  } finally {
    searching.value = false
  }
}

function cycleStatusFilter() {
  statusFilter.value =
    statusFilter.value === 'all' ? 'completed' : statusFilter.value === 'completed' ? 'failed' : 'all'
  message.success(
    statusFilter.value === 'all'
      ? copy.value.filterAll
      : statusFilter.value === 'completed'
        ? copy.value.filterCompleted
        : copy.value.filterFailed
  )
}

function toggleSummaryMode() {
  compactSummary.value = !compactSummary.value
  message.success(compactSummary.value ? copy.value.displayCompact : copy.value.displayFull)
}

function pollTask(id: string) {
  const timer = setInterval(async () => {
    const res = await api.get(`/api/v1/search/tasks/${id}`)
    taskStatus.value = res.data.status
    if (res.data.status === 'completed' || res.data.status === 'done' || res.data.status === 'failed') {
      clearInterval(timer)
      if (res.data.status === 'completed' || res.data.status === 'done') {
        loadReports()
      }
    }
  }, 3000)
}

function formatDate(value?: string) {
  if (!value) return '-'
  const date = new Date(value)
  return locale.isChinese ? date.toLocaleString('zh-CN') : date.toLocaleString('en-US')
}

function reportSource(report: ReportListItem) {
  if (report.quality_score == null) return copy.value.reportSource
  return `${copy.value.reportSource} · ${report.quality_score}`
}
</script>
