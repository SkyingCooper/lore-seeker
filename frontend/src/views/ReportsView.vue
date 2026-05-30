<template>
  <div class="space-y-6">
    <header class="space-y-2">
      <div class="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-neutral-400">
        <img :src="logoMark" alt="Lore Seeker" class="h-4 w-4 object-contain" />
        <span>{{ copy.section }}</span>
      </div>
      <h1 class="text-3xl font-semibold tracking-tight text-neutral-900">{{ copy.title }}</h1>
      <p class="text-sm leading-6 text-neutral-500">{{ copy.subtitle }}</p>
    </header>

    <n-card :bordered="false" class="rounded-[28px] border border-[#dfd7ca] shadow-[0_18px_48px_rgba(148,131,105,0.08)]">
      <n-empty v-if="reports.length === 0" :description="copy.empty" class="py-12">
        <template #icon>
          <div class="flex h-16 w-16 items-center justify-center rounded-3xl bg-[#f5efe6]">
            <FileStack :size="28" class="text-[#7d9ab7]" />
          </div>
        </template>
      </n-empty>

      <n-data-table
        v-else
        :columns="columns"
        :data="reports"
        :bordered="false"
        :single-line="false"
      />
    </n-card>
  </div>
</template>

<script setup lang="ts">
// 文件说明：
// ReportsView 用于展示所有已生成报告的列表视图，适合从时间维度回看历史知识产出。
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { DataTableColumns } from 'naive-ui'
import { NButton, NCard, NDataTable, NEmpty } from 'naive-ui'
import { FileStack } from '@lucide/vue'
import api from '@/api/client'
import logoMark from '@/assets/logo-book.avif'
import { useLocaleStore } from '@/stores/locale'

interface ReportRow {
  id: string
  title: string
  created_at?: string
  quality_score?: number | null
}

const router = useRouter()
const locale = useLocaleStore()
const reports = ref<ReportRow[]>([])

const copy = computed(() =>
  locale.isChinese
    ? {
        section: '归档',
        title: '搜索报告',
        subtitle: '按时间回看已生成的专题报告，快速跳回阅读页继续浏览。',
        empty: '暂无报告',
        titleColumn: '标题',
        dateColumn: '日期',
        scoreColumn: '质量分',
        actionsColumn: '操作',
        view: '查看',
      }
    : {
        section: 'Archive',
        title: 'Search Reports',
        subtitle: 'Review generated reports over time and jump back into the reading view.',
        empty: 'No reports yet',
        titleColumn: 'Title',
        dateColumn: 'Date',
        scoreColumn: 'Quality',
        actionsColumn: 'Actions',
        view: 'Open',
      }
)

const columns = computed<DataTableColumns<ReportRow>>(() => [
  { title: copy.value.titleColumn, key: 'title' },
  {
    title: copy.value.dateColumn,
    key: 'created_at',
    render: (row) => row.created_at?.slice(0, 10) ?? '-',
  },
  {
    title: copy.value.scoreColumn,
    key: 'quality_score',
    render: (row) => row.quality_score ?? '-',
  },
  {
    title: copy.value.actionsColumn,
    key: 'actions',
    render: (row) =>
      h(
        NButton,
        {
          text: true,
          type: 'primary',
          onClick: () => router.push(`/browse/${row.id}`),
        },
        { default: () => copy.value.view }
      ),
  },
])

onMounted(async () => {
  const res = await api.get('/api/v1/reports/')
  reports.value = res.data
})
</script>
