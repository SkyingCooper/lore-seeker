<template>
  <div class="mx-auto max-w-5xl space-y-6 py-8">
    <!-- 任务信息 -->
    <n-card class="rounded-[28px] border-[#dfd7ca] p-6 shadow-md" :bordered="false">
      <div class="flex items-start justify-between">
        <div class="space-y-1">
          <h1 class="text-2xl font-semibold text-neutral-900">{{ task?.topic?.title || `#${task?.id}` }}</h1>
          <p class="text-sm text-neutral-500">{{ task?.topic?.description || copy.noDescription }}</p>
        </div>
        <span class="rounded-full px-3 py-1 text-xs font-medium" :class="statusClass(task?.status)">{{ statusLabel(task?.status) }}</span>
      </div>
      <div class="mt-4 flex flex-wrap gap-2">
        <span v-for="kw in task?.topic?.keywords" :key="kw" class="rounded-lg bg-[#f4ede3] px-2 py-0.5 text-xs text-neutral-600">{{ kw }}</span>
      </div>
      <div class="mt-4 grid gap-3 text-sm text-neutral-500 md:grid-cols-3">
        <div class="rounded-2xl border border-[#e6ddd0] bg-white/75 px-4 py-3">
          <div class="text-xs uppercase tracking-[0.14em] text-neutral-400">{{ copy.query }}</div>
          <div class="mt-1 font-medium text-neutral-800">{{ task?.query || '—' }}</div>
        </div>
        <div class="rounded-2xl border border-[#e6ddd0] bg-white/75 px-4 py-3">
          <div class="text-xs uppercase tracking-[0.14em] text-neutral-400">{{ copy.frequency }}</div>
          <div class="mt-1 font-medium text-neutral-800">{{ freqLabel(task?.frequency) }}</div>
        </div>
        <div class="rounded-2xl border border-[#e6ddd0] bg-white/75 px-4 py-3">
          <div class="text-xs uppercase tracking-[0.14em] text-neutral-400">{{ copy.sourceSites }}</div>
          <div class="mt-1 font-medium text-neutral-800">{{ task?.source_sites?.join(', ') || '—' }}</div>
        </div>
      </div>
      <div class="mt-4 flex gap-3">
        <n-button v-if="task?.status === 'pending'" type="primary" :loading="actionLoading" @click="startTask">{{ copy.start }}</n-button>
        <n-button v-if="task?.status === 'pending' && task?.frequency !== 'once'" secondary :loading="actionLoading" @click="submitTask">{{ copy.submit }}</n-button>
        <n-button v-if="task?.status === 'failed'" secondary @click="retryTask">{{ copy.retry }}</n-button>
        <n-button secondary :loading="loading" @click="loadData">{{ copy.refresh }}</n-button>
        <n-button v-if="!auth.isGuest" tertiary @click="deleteTask">{{ copy.delete }}</n-button>
      </div>
    </n-card>

    <!-- 报告列表 -->
    <div class="space-y-3">
      <h2 class="text-lg font-semibold text-neutral-800">{{ copy.reports }}</h2>
      <div v-if="reports.length === 0" class="py-6 text-center text-sm text-neutral-400">{{ copy.noReports }}</div>
      <div
        v-for="r in reports"
        :key="r.id"
        class="flex cursor-pointer items-center gap-4 rounded-xl border border-[#e6ddd0] bg-white/70 p-4 transition hover:shadow-sm"
        @click="router.push(`/browse/${r.id}`)"
      >
        <div class="min-w-0 flex-1">
          <div class="text-sm font-medium text-neutral-800">{{ copy.reportNo }} #{{ r.id }}</div>
          <div class="mt-1 flex gap-3 text-xs text-neutral-400">
            <span>{{ r.created_at ? formatDate(r.created_at) : '-' }}</span>
            <span v-if="r.result_count">· {{ r.result_count }} {{ copy.results }}</span>
            <span v-if="r.quality_score != null">· {{ copy.score }}: {{ r.quality_score }}</span>
          </div>
        </div>
        <span class="rounded-full px-2.5 py-0.5 text-xs font-medium" :class="reportStatusClass(r.status)">{{ reportStatusLabel(r.status) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NCard, useDialog, useMessage } from 'naive-ui'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useLocaleStore } from '@/stores/locale'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const dialog = useDialog()
const locale = useLocaleStore()
const auth = useAuthStore()
const task = ref<any>(null)
const reports = ref<any[]>([])
const loading = ref(false)
const actionLoading = ref(false)
let pollTimer: number | null = null

onMounted(async () => {
  await loadData()
  if (['fetching', 'organizing'].includes(task.value?.status)) {
    startPolling()
  }
})
onBeforeUnmount(stopPolling)

async function loadData() {
  const id = route.params.id as string
  loading.value = true
  try {
    const [t, r] = await Promise.all([
      api.get(`/api/v1/tasks/${id}`),
      api.get(`/api/v1/reports?task_id=${id}`),
    ])
    task.value = t.data
    reports.value = r.data
  } finally {
    loading.value = false
  }
}

async function startTask() {
  if (!task.value) return
  actionLoading.value = true
  try {
    await api.post(`/api/v1/tasks/${task.value.id}/start`)
    task.value.status = 'fetching'
    message.success(locale.isChinese ? '任务已启动' : 'Task started')
    startPolling()
  } catch (e: any) {
    message.error(e.response?.data?.detail?.detail || 'Failed')
  } finally {
    actionLoading.value = false
  }
}

async function submitTask() {
  if (!task.value) return
  actionLoading.value = true
  try {
    await api.post(`/api/v1/tasks/${task.value.id}/submit`)
    message.success(locale.isChinese ? '任务已提交' : 'Task submitted')
    await loadData()
    if (['fetching', 'organizing'].includes(task.value?.status)) startPolling()
  } catch (e: any) {
    message.error(e.response?.data?.detail?.detail || 'Failed')
  } finally {
    actionLoading.value = false
  }
}

async function retryTask() {
  if (!task.value) return
  try {
    await api.post(`/api/v1/tasks/${task.value.id}/retry`)
    task.value.status = 'pending'
    message.success(locale.isChinese ? '任务已加入重试队列' : 'Task queued for retry')
  } catch (e: any) {
    message.error(e.response?.data?.detail?.detail || 'Failed')
  }
}

function deleteTask() {
  if (!task.value) return
  dialog.warning({
    title: locale.isChinese ? '删除任务' : 'Delete task',
    content: locale.isChinese ? '删除后当前任务将从列表中移除。' : 'The task will be removed from active lists.',
    positiveText: locale.isChinese ? '删除' : 'Delete',
    negativeText: locale.isChinese ? '取消' : 'Cancel',
    async onPositiveClick() {
      try {
        await api.delete(`/api/v1/tasks/${task.value.id}`)
        message.success(locale.isChinese ? '任务已删除' : 'Task deleted')
        router.push('/tasks')
      } catch (e: any) {
        message.error(e.response?.data?.detail?.detail || 'Failed')
      }
    },
  })
}

function startPolling() {
  stopPolling()
  pollTimer = window.setInterval(async () => {
    await loadData()
    if (!['fetching', 'organizing'].includes(task.value?.status)) {
      stopPolling()
    }
  }, 3000)
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

function statusClass(s: string) {
  const m: Record<string,string> = { pending:'bg-amber-50 text-amber-600', fetching:'bg-blue-50 text-blue-600', organizing:'bg-purple-50 text-purple-600', completed:'bg-emerald-50 text-emerald-600', failed:'bg-red-50 text-red-600' }
  return m[s]||'bg-neutral-100 text-neutral-500'
}
function statusLabel(s: string) {
  if (!s) return ''
  return locale.isChinese ? { pending:'未开始',fetching:'抓取中',organizing:'梳理中',completed:'已结束',failed:'失败' }[s]||s : { pending:'Pending',fetching:'Fetching',organizing:'Organizing',completed:'Done',failed:'Failed' }[s]||s
}
function reportStatusClass(s: string) {
  const m: Record<string,string> = { completed:'bg-emerald-50 text-emerald-600', partial:'bg-amber-50 text-amber-600', failed:'bg-red-50 text-red-600', success:'bg-emerald-50 text-emerald-600' }
  return m[s]||'bg-neutral-100 text-neutral-500'
}
function reportStatusLabel(s: string) {
  if (!s) return ''
  return locale.isChinese ? { completed:'全部成功',partial:'部分成功',failed:'失败',success:'成功' }[s]||s : { completed:'All success',partial:'Partial',failed:'Failed',success:'Success' }[s]||s
}
function formatDate(iso: string) { return new Date(iso).toLocaleDateString() }
function freqLabel(f: string) {
  const zh = locale.isChinese
  const m: Record<string, string> = zh
    ? { once: '一次', daily: '每天', weekly: '每周', biweekly: '每两周', monthly: '每月' }
    : { once: 'Once', daily: 'Daily', weekly: 'Weekly', biweekly: 'Bi-weekly', monthly: 'Monthly' }
  return m[f] || f
}

const copy = locale.isChinese
  ? { noDescription:'暂无描述', start:'开始执行', submit:'提交计划', retry:'重新执行', refresh:'刷新', delete:'删除任务', reports:'执行报告', noReports:'暂无报告', reportNo:'报告', results:'条结果', score:'评分', query:'查询词', frequency:'频率', sourceSites:'来源站点' }
  : { noDescription:'No description', start:'Start', submit:'Submit', retry:'Retry', refresh:'Refresh', delete:'Delete', reports:'Reports', noReports:'No reports yet', reportNo:'Report', results:'results', score:'Score', query:'Query', frequency:'Frequency', sourceSites:'Source sites' }
</script>
