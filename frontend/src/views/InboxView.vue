<template>
  <div class="space-y-6">
    <header class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div class="space-y-2">
        <div class="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-neutral-400">
          <Inbox :size="14" class="text-[#8ca0b5]" />
          <span>{{ copy.section }}</span>
        </div>
        <h1 class="text-4xl font-semibold tracking-tight text-neutral-900">{{ copy.title }}</h1>
        <p class="max-w-2xl text-sm leading-7 text-neutral-500">{{ copy.subtitle }}</p>
      </div>

      <n-button secondary class="rounded-2xl" :loading="loading" @click="loadTasks">
        <template #icon>
          <RefreshCw :size="16" />
        </template>
        {{ copy.refresh }}
      </n-button>
    </header>

    <section class="rounded-[28px] border border-[#dfd7ca] bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(255,251,245,0.96))] p-5 shadow-[0_18px_48px_rgba(148,131,105,0.08)]">
      <n-empty v-if="notifications.length === 0 && !loading" :description="copy.empty" class="py-10">
        <template #icon>
          <div class="flex h-16 w-16 items-center justify-center rounded-[22px] bg-[#f7efe5] text-[#7b92ab]">
            <Inbox :size="28" />
          </div>
        </template>
      </n-empty>

      <div v-else class="space-y-3">
        <button
          v-for="item in notifications"
          :key="item.id"
          class="flex w-full items-start gap-4 rounded-2xl border border-[#e8dfd3] bg-white/80 px-4 py-4 text-left transition hover:bg-[#fffaf2] hover:shadow-[0_10px_28px_rgba(148,131,105,0.08)]"
          @click="router.push(`/tasks/${item.task.id}`)"
        >
          <div
            class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl"
            :class="item.iconClass"
          >
            <component :is="item.icon" :size="21" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <div class="truncate text-[15px] font-semibold text-neutral-900">{{ item.title }}</div>
              <span class="rounded-full px-2.5 py-0.5 text-xs font-medium" :class="statusClass(item.task.status)">
                {{ statusLabel(item.task.status) }}
              </span>
            </div>
            <div class="mt-1 text-sm leading-6 text-neutral-500">{{ item.body }}</div>
            <div class="mt-2 text-xs text-neutral-400">{{ formatDate(item.task.updated_at || item.task.created_at) }}</div>
          </div>
          <ChevronRight :size="16" class="mt-3 text-neutral-300" />
        </button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
// 文件说明：
// InboxView 使用 /api/v1/tasks 聚合任务通知，把完成、失败和执行中的任务变成可点击消息。
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NEmpty } from 'naive-ui'
import { AlertTriangle, CheckCircle2, ChevronRight, Inbox, Loader2, RefreshCw } from '@lucide/vue'
import api from '@/api/client'
import { useLocaleStore } from '@/stores/locale'

interface TaskItem {
  id: number | string
  topic_title?: string
  status: string
  created_at?: string
  updated_at?: string
}

const router = useRouter()
const locale = useLocaleStore()
const loading = ref(false)
const tasks = ref<TaskItem[]>([])

const copy = computed(() =>
  locale.isChinese
    ? {
        section: '收件箱',
        title: '收件箱',
        subtitle: '集中查看任务完成提醒、失败提醒和正在执行的研究任务。',
        empty: '暂时没有新的通知。',
        refresh: '刷新',
        completed: '任务已完成',
        failed: '任务执行失败',
        running: '任务正在执行',
        pending: '任务等待执行',
        completedBody: '报告已经生成，可以点击查看任务详情和报告。',
        failedBody: '执行过程中发生错误，可以进入任务详情重新执行。',
        runningBody: 'Agent 正在搜索或整理资料。',
        pendingBody: '任务已经创建，等待开始执行。',
      }
    : {
        section: 'Inbox',
        title: 'Inbox',
        subtitle: 'Review completed, failed, and active research tasks in one place.',
        empty: 'No new notifications yet.',
        refresh: 'Refresh',
        completed: 'Task completed',
        failed: 'Task failed',
        running: 'Task in progress',
        pending: 'Task pending',
        completedBody: 'A report is ready. Open the task to review details and reports.',
        failedBody: 'The run failed. Open the task to retry it.',
        runningBody: 'Agents are searching or organizing materials.',
        pendingBody: 'The task has been created and is waiting to run.',
      }
)

const notifications = computed(() =>
  tasks.value
    .filter((task) => ['completed', 'failed', 'fetching', 'organizing', 'pending'].includes(task.status))
    .slice(0, 20)
    .map((task) => {
      if (task.status === 'completed') {
        return {
          id: `task-${task.id}-completed`,
          task,
          title: `${copy.value.completed} · ${task.topic_title || `#${task.id}`}`,
          body: copy.value.completedBody,
          icon: CheckCircle2,
          iconClass: 'bg-emerald-50 text-emerald-600',
        }
      }
      if (task.status === 'failed') {
        return {
          id: `task-${task.id}-failed`,
          task,
          title: `${copy.value.failed} · ${task.topic_title || `#${task.id}`}`,
          body: copy.value.failedBody,
          icon: AlertTriangle,
          iconClass: 'bg-red-50 text-red-600',
        }
      }
      if (task.status === 'fetching' || task.status === 'organizing') {
        return {
          id: `task-${task.id}-running`,
          task,
          title: `${copy.value.running} · ${task.topic_title || `#${task.id}`}`,
          body: copy.value.runningBody,
          icon: Loader2,
          iconClass: 'bg-blue-50 text-blue-600',
        }
      }
      return {
        id: `task-${task.id}-pending`,
        task,
        title: `${copy.value.pending} · ${task.topic_title || `#${task.id}`}`,
        body: copy.value.pendingBody,
        icon: Inbox,
        iconClass: 'bg-amber-50 text-amber-600',
      }
    })
)

onMounted(loadTasks)

async function loadTasks() {
  loading.value = true
  try {
    const res = await api.get('/api/v1/tasks')
    tasks.value = res.data
  } finally {
    loading.value = false
  }
}

function statusClass(status: string) {
  return {
    pending: 'bg-amber-50 text-amber-600',
    fetching: 'bg-blue-50 text-blue-600',
    organizing: 'bg-purple-50 text-purple-600',
    completed: 'bg-emerald-50 text-emerald-600',
    failed: 'bg-red-50 text-red-600',
  }[status] || 'bg-neutral-100 text-neutral-500'
}

function statusLabel(status: string) {
  const zh = locale.isChinese
  const labels: Record<string, string> = zh
    ? { pending: '未开始', fetching: '抓取中', organizing: '梳理中', completed: '已完成', failed: '失败' }
    : { pending: 'Pending', fetching: 'Fetching', organizing: 'Organizing', completed: 'Done', failed: 'Failed' }
  return labels[status] || status
}

function formatDate(value?: string) {
  if (!value) return '-'
  const date = new Date(value)
  return locale.isChinese ? date.toLocaleString('zh-CN') : date.toLocaleString('en-US')
}
</script>
