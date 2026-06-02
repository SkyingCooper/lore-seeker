<template>
  <div class="mx-auto max-w-5xl space-y-6 py-8">
    <header class="flex items-center justify-between">
      <div class="space-y-2">
        <h1 class="text-4xl font-semibold tracking-tight text-neutral-900">{{ copy.title }}</h1>
        <p class="text-sm text-neutral-500">{{ copy.subtitle }}</p>
      </div>
      <n-button type="primary" size="large" class="rounded-2xl" @click="router.push('/tasks/new')">
        <template #icon><Plus :size="18" /></template>
        {{ copy.create }}
      </n-button>
    </header>

    <n-card v-if="tasks.length === 0 && !loading" class="rounded-[28px] border-[#dfd7ca] p-10 shadow-md" :bordered="false">
      <div class="text-center text-neutral-400">
        <p class="text-lg">{{ copy.empty }}</p>
        <p class="mt-2 text-sm">{{ copy.emptyHint }}</p>
      </div>
    </n-card>

    <div v-else class="space-y-3">
      <div
        v-for="task in tasks"
        :key="task.id"
        class="flex cursor-pointer items-center gap-4 rounded-2xl border border-[#e6ddd0] bg-white/80 p-5 transition hover:shadow-md"
        @click="router.push(`/tasks/${task.id}`)"
      >
        <div class="min-w-0 flex-1">
          <div class="text-base font-semibold text-neutral-800">{{ task.topic_title || `#${task.id}` }}</div>
          <div class="mt-1 flex items-center gap-3 text-xs text-neutral-400">
            <span>{{ task.search_mode }}</span>
            <span>·</span>
            <span>{{ freqLabel(task.frequency) }}</span>
            <span v-if="task.created_at">· {{ formatDate(task.created_at) }}</span>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <span class="rounded-full px-3 py-1 text-xs font-medium" :class="statusClass(task.status)">{{ statusLabel(task.status) }}</span>
          <ChevronRight :size="16" class="text-neutral-300" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NCard } from 'naive-ui'
import { ChevronRight, Plus } from '@lucide/vue'
import api from '@/api/client'
import { useLocaleStore } from '@/stores/locale'

const locale = useLocaleStore()
const router = useRouter()
const tasks = ref<any[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await api.get('/api/v1/tasks')
    tasks.value = res.data
  } catch { /* ignore */ }
  loading.value = false
})

function statusClass(s: string) {
  return {
    pending: 'bg-amber-50 text-amber-600',
    fetching: 'bg-blue-50 text-blue-600',
    organizing: 'bg-purple-50 text-purple-600',
    completed: 'bg-emerald-50 text-emerald-600',
    failed: 'bg-red-50 text-red-600',
  }[s] || 'bg-neutral-100 text-neutral-500'
}

function statusLabel(s: string) {
  const zh = locale.isChinese
  const m: Record<string, string> = zh
    ? { pending: '未开始', fetching: '抓取中', organizing: '梳理中', completed: '已结束', failed: '失败' }
    : { pending: 'Pending', fetching: 'Fetching', organizing: 'Organizing', completed: 'Done', failed: 'Failed' }
  return m[s] || s
}

function freqLabel(f: string) {
  const zh = locale.isChinese
  const m: Record<string, string> = zh
    ? { once: '一次', daily: '每天', weekly: '每周', biweekly: '每两周', monthly: '每月' }
    : { once: 'Once', daily: 'Daily', weekly: 'Weekly', biweekly: 'Bi-weekly', monthly: 'Monthly' }
  return m[f] || f
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString()
}

const copy = computed(() =>
  locale.isChinese
    ? { title: '任务列表', subtitle: '管理你的搜索任务，查看执行状态和报告。', create: '新建任务', empty: '暂无任务', emptyHint: '点击右上角创建你的第一个搜索任务' }
    : { title: 'Tasks', subtitle: 'Manage your search tasks, view execution status and reports.', create: 'New Task', empty: 'No tasks yet', emptyHint: 'Click the button above to create your first task' }
)
</script>
