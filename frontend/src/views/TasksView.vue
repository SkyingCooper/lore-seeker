<template>
  <div class="mx-auto max-w-5xl space-y-6 py-8">
    <header class="flex items-center justify-between gap-3">
      <div class="space-y-2">
        <h1 class="text-4xl font-semibold tracking-tight text-neutral-900">{{ copy.title }}</h1>
        <p class="text-sm text-neutral-500">{{ copy.subtitle }}</p>
      </div>
      <div class="flex items-center gap-3">
        <n-button secondary size="large" class="rounded-2xl" :loading="loading" @click="loadTasks">
          <template #icon><RefreshCw :size="18" /></template>
          {{ copy.refresh }}
        </n-button>
        <n-button type="primary" size="large" class="rounded-2xl" @click="router.push('/tasks/new')">
          <template #icon><Plus :size="18" /></template>
          {{ copy.create }}
        </n-button>
      </div>
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
            <template v-if="task.source_sites?.length">
              <span>·</span>
              <span>{{ task.source_sites.slice(0, 2).join(', ') }}</span>
            </template>
            <span v-if="task.created_at">· {{ formatDate(task.created_at) }}</span>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <div class="hidden items-center gap-2 md:flex">
            <n-button
              v-if="task.status === 'pending'"
              size="small"
              secondary
              class="rounded-xl"
              @click.stop="startTask(task)"
            >
              {{ copy.start }}
            </n-button>
            <n-button
              v-if="task.status === 'failed'"
              size="small"
              secondary
              class="rounded-xl"
              @click.stop="retryTask(task)"
            >
              {{ copy.retry }}
            </n-button>
            <n-button
              v-if="!isGuest"
              size="small"
              quaternary
              class="rounded-xl"
              @click.stop="deleteTask(task)"
            >
              {{ copy.delete }}
            </n-button>
          </div>
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
import { NButton, NCard, useDialog, useMessage } from 'naive-ui'
import { ChevronRight, Plus, RefreshCw } from '@lucide/vue'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useLocaleStore } from '@/stores/locale'

const locale = useLocaleStore()
const auth = useAuthStore()
const router = useRouter()
const message = useMessage()
const dialog = useDialog()
const tasks = ref<any[]>([])
const loading = ref(true)

onMounted(loadTasks)

async function loadTasks() {
  loading.value = true
  try {
    const res = await api.get('/api/v1/tasks')
    tasks.value = res.data
  } catch {
    // ignore
  }
  loading.value = false
}

const isGuest = computed(() => auth.isGuest)

async function startTask(task: any) {
  try {
    await api.post(`/api/v1/tasks/${task.id}/start`)
    message.success(locale.isChinese ? '任务已启动' : 'Task started')
    await loadTasks()
  } catch (e: any) {
    message.error(e.response?.data?.detail?.detail || (locale.isChinese ? '启动失败' : 'Failed to start task'))
  }
}

async function retryTask(task: any) {
  try {
    await api.post(`/api/v1/tasks/${task.id}/retry`)
    message.success(locale.isChinese ? '任务已加入重试队列' : 'Task queued for retry')
    await loadTasks()
  } catch (e: any) {
    message.error(e.response?.data?.detail?.detail || (locale.isChinese ? '重试失败' : 'Failed to retry task'))
  }
}

function deleteTask(task: any) {
  dialog.warning({
    title: locale.isChinese ? '删除任务' : 'Delete task',
    content: locale.isChinese ? '删除后任务会进入逻辑删除状态，当前列表将不再显示。' : 'The task will be soft-deleted and removed from this list.',
    positiveText: locale.isChinese ? '删除' : 'Delete',
    negativeText: locale.isChinese ? '取消' : 'Cancel',
    async onPositiveClick() {
      try {
        await api.delete(`/api/v1/tasks/${task.id}`)
        message.success(locale.isChinese ? '任务已删除' : 'Task deleted')
        await loadTasks()
      } catch (e: any) {
        message.error(e.response?.data?.detail?.detail || (locale.isChinese ? '删除失败' : 'Failed to delete task'))
      }
    },
  })
}

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
    ? { title: '任务列表', subtitle: '管理你的搜索任务，查看执行状态和报告。', create: '新建任务', refresh: '刷新', start: '启动', retry: '重试', delete: '删除', empty: '暂无任务', emptyHint: '点击右上角创建你的第一个搜索任务' }
    : { title: 'Tasks', subtitle: 'Manage your search tasks, view execution status and reports.', create: 'New Task', refresh: 'Refresh', start: 'Start', retry: 'Retry', delete: 'Delete', empty: 'No tasks yet', emptyHint: 'Click the button above to create your first task' }
)
</script>
