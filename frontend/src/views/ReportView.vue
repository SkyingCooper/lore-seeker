<template>
  <div v-if="report" class="grid gap-6 xl:grid-cols-[260px_minmax(0,1fr)]">
    <aside class="xl:sticky xl:top-8 xl:self-start">
      <div class="rounded-[26px] border border-[#dfd9cf] bg-[var(--ls-panel)] p-4 shadow-[0_18px_48px_rgba(148,131,105,0.08)]">
        <div class="mb-4 space-y-2">
          <div class="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-neutral-400">
            <img :src="logoMark" alt="Lore Seeker" class="h-4 w-4 object-contain" />
            <span>{{ copy.section }}</span>
          </div>
          <h1 class="text-lg font-semibold leading-7 text-neutral-900">{{ report.title }}</h1>
          <p class="text-sm leading-6 text-neutral-500">{{ report.summary || copy.emptySummary }}</p>
        </div>

        <div class="mb-4 space-y-2 rounded-2xl bg-[#f3ede4] px-3 py-3 text-xs leading-6 text-neutral-600">
          <div class="flex items-center gap-2">
            <Clock3 :size="14" class="text-[#8ca0b5]" />
            <span>{{ copy.createdAt }}: {{ formatDate(report.created_at) }}</span>
          </div>
          <div class="flex items-center gap-2">
            <ListTree :size="14" class="text-[#8ca0b5]" />
            <span>{{ copy.tocCount }}: {{ report.toc.length }}</span>
          </div>
        </div>

        <div class="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-neutral-400">
          <BookMarked :size="14" class="text-[#8ca0b5]" />
          <span>{{ copy.toc }}</span>
        </div>
        <div class="space-y-1">
          <button
            v-for="item in report.toc"
            :key="item.anchor"
            class="block w-full rounded-xl px-3 py-2 text-left text-sm transition hover:bg-[#f2ece2]"
            :class="item.level === 3 ? 'pl-7 text-neutral-500' : 'font-medium text-neutral-800'"
            @click="scrollTo(item.anchor)"
          >
            {{ item.title }}
          </button>
        </div>
      </div>
    </aside>

    <section class="rounded-[28px] border border-[#dfd9cf] bg-[var(--ls-panel)] shadow-[0_18px_48px_rgba(148,131,105,0.08)]">
      <div class="border-b border-[#e5ddd2] px-6 py-5 lg:px-10">
        <div class="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-neutral-400">
          <NotebookText :size="14" class="text-[#8ca0b5]" />
          <span>{{ copy.reader }}</span>
        </div>
        <div class="mt-2 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 class="text-3xl font-semibold tracking-tight text-neutral-900">{{ report.title }}</h2>
            <p class="mt-2 max-w-3xl text-sm leading-7 text-neutral-500">{{ report.summary || copy.readerHint }}</p>
          </div>
          <n-button secondary @click="router.push('/browse')">
            <template #icon>
              <ArrowLeft :size="16" />
            </template>
            {{ copy.backHome }}
          </n-button>
        </div>
      </div>

      <div class="grid gap-4 border-b border-[#e5ddd2] px-6 py-5 lg:grid-cols-4 lg:px-10">
        <div class="rounded-2xl bg-[#f6efe5] px-4 py-3">
          <div class="text-xs uppercase tracking-[0.14em] text-neutral-400">{{ copy.quality }}</div>
          <div class="mt-1 text-lg font-semibold text-neutral-900">{{ report.quality_score ?? '—' }}</div>
        </div>
        <div class="rounded-2xl bg-[#f6efe5] px-4 py-3">
          <div class="text-xs uppercase tracking-[0.14em] text-neutral-400">{{ copy.results }}</div>
          <div class="mt-1 text-lg font-semibold text-neutral-900">{{ report.result_count ?? 0 }}</div>
        </div>
        <div class="rounded-2xl bg-[#f6efe5] px-4 py-3">
          <div class="text-xs uppercase tracking-[0.14em] text-neutral-400">{{ copy.tokens }}</div>
          <div class="mt-1 text-lg font-semibold text-neutral-900">{{ report.token_usage?.total ?? 0 }}</div>
        </div>
        <div class="rounded-2xl bg-[#f6efe5] px-4 py-3">
          <div class="text-xs uppercase tracking-[0.14em] text-neutral-400">{{ copy.cost }}</div>
          <div class="mt-1 text-lg font-semibold text-neutral-900">${{ formatUsd(report.cost_usage?.total_usd) }}</div>
        </div>
      </div>

      <div class="grid gap-5 border-b border-[#e5ddd2] px-6 py-5 lg:grid-cols-[minmax(0,1fr)_320px] lg:px-10">
        <div>
          <div class="mb-2 text-sm font-semibold text-neutral-900">{{ copy.tokenBreakdown }}</div>
          <div v-if="tokenRows.length === 0" class="text-sm text-neutral-400">{{ copy.emptyUsage }}</div>
          <div v-else class="space-y-2">
            <div v-for="row in tokenRows" :key="row.key" class="rounded-2xl border border-[#ebe2d6] bg-white/80 px-4 py-3">
              <div class="flex items-center justify-between gap-3">
                <div class="font-medium text-neutral-900">{{ row.key }}</div>
                <div class="text-sm text-neutral-500">{{ row.model || '—' }}</div>
              </div>
              <div class="mt-2 grid gap-2 text-sm text-neutral-600 md:grid-cols-3">
                <div>{{ copy.input }}: {{ row.input_tokens ?? 0 }}</div>
                <div>{{ copy.output }}: {{ row.output_tokens ?? 0 }}</div>
                <div>{{ copy.total }}: {{ row.total ?? 0 }}</div>
              </div>
            </div>
          </div>
        </div>

        <div>
          <div class="mb-2 text-sm font-semibold text-neutral-900">{{ copy.feedback }}</div>
          <div class="rounded-2xl border border-[#ebe2d6] bg-white/80 p-4">
            <div class="flex flex-wrap gap-2">
              <n-button v-for="option in satisfactionOptions" :key="option.value" secondary size="small" @click="submitEvaluation(option.value)">
                {{ option.label }}
              </n-button>
            </div>
            <n-input v-model:value="feedbackNotes" class="mt-3" type="textarea" :rows="4" :placeholder="copy.feedbackPlaceholder" />
            <div class="mt-3 flex items-center justify-between gap-3 text-xs text-neutral-400">
              <span>{{ copy.currentSatisfaction }}: {{ report.user_satisfaction || '—' }}</span>
            </div>
          </div>
        </div>
      </div>

      <article class="px-4 py-6 lg:px-10">
        <MdPreview :modelValue="report.content_md" theme="light" codeTheme="github" />
      </article>
    </section>
  </div>

  <div v-else class="rounded-2xl border border-[#dfd9cf] bg-[var(--ls-panel)] px-6 py-14 text-center text-neutral-500">
    {{ copy.loading }}
  </div>
</template>

<script setup lang="ts">
// 文件说明：
// ReportView 负责单篇报告的阅读体验，包含目录导航、元信息展示和 Markdown 正文渲染。
// 该页面沿用“左侧结构导航 + 右侧正文”的知识阅读模式，并接入中英文文案切换。
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NInput, useMessage } from 'naive-ui'
import { ArrowLeft, BookMarked, Clock3, ListTree, NotebookText } from '@lucide/vue'
import { MdPreview } from 'md-editor-v3'
import logoMark from '@/assets/logo-book.avif'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useLocaleStore } from '@/stores/locale'

interface TocItem {
  level: number
  title: string
  anchor: string
}

interface ReportDetail {
  id: string
  title: string
  content_md: string
  toc: TocItem[]
  summary: string | null
  result_count?: number | null
  quality_score?: number | null
  token_usage?: any
  cost_usage?: any
  user_satisfaction?: string | null
  satisfaction_notes?: string | null
  created_at?: string
}

const route = useRoute()
const router = useRouter()
const locale = useLocaleStore()
const auth = useAuthStore()
const message = useMessage()
const report = ref<ReportDetail | null>(null)
const feedbackNotes = ref('')

const copy = computed(() =>
  locale.isChinese
    ? {
        section: '报告',
        emptySummary: '暂无摘要',
        createdAt: '创建时间',
        tocCount: '目录项',
        toc: '目录',
        reader: '阅读器',
        readerHint: '这份报告已经写入知识库，可以在这里按章节阅读和回看整理结果。',
        backHome: '返回首页',
        loading: '加载中...',
        quality: '质量分',
        results: '结果数',
        tokens: 'Token',
        cost: '外部成本',
        tokenBreakdown: 'Token 分环节明细',
        emptyUsage: '暂无资源消耗明细。',
        input: '输入',
        output: '输出',
        total: '合计',
        feedback: '满意度反馈',
        feedbackPlaceholder: '可选：记录不满意原因或建议',
        currentSatisfaction: '当前评价',
        evalSaved: '评价已保存',
      }
    : {
        section: 'Report',
        emptySummary: 'No summary yet',
        createdAt: 'Created',
        tocCount: 'TOC items',
        toc: 'Table of contents',
        reader: 'Reader',
        readerHint: 'This report has been stored in the knowledge base and can be reviewed section by section here.',
        backHome: 'Back to home',
        loading: 'Loading...',
        quality: 'Quality',
        results: 'Results',
        tokens: 'Tokens',
        cost: 'External cost',
        tokenBreakdown: 'Token usage by stage',
        emptyUsage: 'No usage details yet.',
        input: 'Input',
        output: 'Output',
        total: 'Total',
        feedback: 'Satisfaction',
        feedbackPlaceholder: 'Optional notes about the result quality',
        currentSatisfaction: 'Current rating',
        evalSaved: 'Feedback saved',
      }
)

onMounted(async () => {
  const res = await api.get(`/api/v1/reports/${route.params.reportId}`)
  report.value = res.data
  feedbackNotes.value = res.data.satisfaction_notes || ''
})

const tokenRows = computed(() => {
  const breakdown = report.value?.token_usage?.breakdown || {}
  const modelUsed = report.value?.token_usage?.model_used || {}
  return Object.entries(breakdown).map(([key, value]: [string, any]) => ({
    key,
    model: modelUsed[key] ?? null,
    ...(value || {}),
  }))
})

const satisfactionOptions = computed(() =>
  locale.isChinese
    ? [
        { value: 'satisfied', label: '满意' },
        { value: 'neutral', label: '一般' },
        { value: 'dissatisfied', label: '不满意' },
      ]
    : [
        { value: 'satisfied', label: 'Satisfied' },
        { value: 'neutral', label: 'Neutral' },
        { value: 'dissatisfied', label: 'Dissatisfied' },
      ]
)

function scrollTo(anchor: string) {
  const el = document.getElementById(anchor)
  el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function formatDate(value?: string) {
  if (!value) return '-'
  const date = new Date(value)
  return locale.isChinese ? date.toLocaleString('zh-CN') : date.toLocaleString('en-US')
}

function formatUsd(value?: number | null) {
  return (value ?? 0).toFixed(3)
}

async function submitEvaluation(satisfaction: string) {
  if (!report.value || auth.isGuest) return
  await api.post(`/api/v1/reports/${report.value.id}/evaluate`, {
    satisfaction,
    notes: feedbackNotes.value || null,
  })
  report.value.user_satisfaction = satisfaction
  report.value.satisfaction_notes = feedbackNotes.value || null
  message.success(copy.value.evalSaved)
}
</script>
