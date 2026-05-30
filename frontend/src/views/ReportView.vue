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
import { NButton } from 'naive-ui'
import { ArrowLeft, BookMarked, Clock3, ListTree, NotebookText } from '@lucide/vue'
import { MdPreview } from 'md-editor-v3'
import logoMark from '@/assets/logo-book.avif'
import api from '@/api/client'
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
  created_at?: string
}

const route = useRoute()
const router = useRouter()
const locale = useLocaleStore()
const report = ref<ReportDetail | null>(null)

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
      }
)

onMounted(async () => {
  const res = await api.get(`/api/v1/reports/${route.params.reportId}`)
  report.value = res.data
})

function scrollTo(anchor: string) {
  const el = document.getElementById(anchor)
  el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function formatDate(value?: string) {
  if (!value) return '-'
  const date = new Date(value)
  return locale.isChinese ? date.toLocaleString('zh-CN') : date.toLocaleString('en-US')
}
</script>
