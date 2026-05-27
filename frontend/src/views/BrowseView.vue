<template>
  <div class="browse">
    <div class="search-bar">
      <input v-model="query" placeholder="输入搜索主题..." @keyup.enter="startSearch" />
      <select v-model="searchMode">
        <option value="api">API 搜索</option>
        <option value="crawl">爬虫扫描</option>
        <option value="both">混合模式</option>
      </select>
      <button @click="startSearch" :disabled="searching">
        {{ searching ? '搜索中...' : '开始搜索' }}
      </button>
    </div>

    <div v-if="taskId" class="task-status">
      任务 {{ taskId.slice(0, 8) }}... 状态：{{ taskStatus }}
    </div>

    <div class="report-list">
      <div v-if="reports.length === 0" class="empty">暂无报告，开始第一次搜索吧</div>
      <div v-for="r in reports" :key="r.id" class="report-card" @click="$router.push(`/browse/${r.id}`)">
        <h3>{{ r.title }}</h3>
        <p>{{ r.summary || '暂无摘要' }}</p>
        <span class="meta">{{ r.created_at?.slice(0, 10) }} · 质量分 {{ r.quality_score ?? '-' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api/client'

const query = ref('')
const searchMode = ref('api')
const searching = ref(false)
const taskId = ref<string | null>(null)
const taskStatus = ref('')
const reports = ref<any[]>([])

onMounted(loadReports)

async function loadReports() {
  const res = await api.get('/api/v1/reports/')
  reports.value = res.data
}

async function startSearch() {
  if (!query.value.trim()) return
  searching.value = true
  try {
    const res = await api.post('/api/v1/search/start', { query: query.value, search_mode: searchMode.value })
    taskId.value = res.data.task_id
    taskStatus.value = 'pending'
    pollTask(res.data.task_id)
  } finally {
    searching.value = false
  }
}

function pollTask(id: string) {
  const timer = setInterval(async () => {
    const res = await api.get(`/api/v1/search/tasks/${id}`)
    taskStatus.value = res.data.status
    if (res.data.status === 'done' || res.data.status === 'failed') {
      clearInterval(timer)
      if (res.data.status === 'done') loadReports()
    }
  }, 3000)
}
</script>

<style scoped>
.browse { padding: 32px; max-width: 900px; margin: 0 auto; }
.search-bar { display: flex; gap: 10px; margin-bottom: 24px; }
.search-bar input { flex: 1; padding: 10px 14px; border: 1px solid #ddd; border-radius: 8px; font-size: 15px; }
.search-bar select { padding: 10px; border: 1px solid #ddd; border-radius: 8px; }
.search-bar button { padding: 10px 20px; background: #7c83fd; color: #fff; border: none; border-radius: 8px; cursor: pointer; }
.task-status { padding: 10px 16px; background: #fffbe6; border: 1px solid #ffe58f; border-radius: 8px; margin-bottom: 16px; font-size: 13px; }
.report-card { background: #fff; border-radius: 10px; padding: 20px; margin-bottom: 14px; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,.06); transition: box-shadow .2s; }
.report-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,.12); }
.report-card h3 { margin: 0 0 8px; font-size: 16px; }
.report-card p { margin: 0 0 8px; color: #666; font-size: 14px; }
.meta { font-size: 12px; color: #999; }
.empty { text-align: center; color: #aaa; padding: 60px 0; }
</style>
