<template>
  <div class="reports">
    <h2>搜索报告</h2>
    <div v-if="reports.length === 0" class="empty">暂无报告</div>
    <table v-else>
      <thead>
        <tr><th>标题</th><th>日期</th><th>质量分</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="r in reports" :key="r.id">
          <td>{{ r.title }}</td>
          <td>{{ r.created_at?.slice(0, 10) }}</td>
          <td>{{ r.quality_score ?? '-' }}</td>
          <td><a @click="$router.push(`/browse/${r.id}`)">查看</a></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api/client'

const reports = ref<any[]>([])
onMounted(async () => {
  const res = await api.get('/api/v1/reports/')
  reports.value = res.data
})
</script>

<style scoped>
.reports { padding: 32px; }
h2 { margin-bottom: 24px; }
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,.06); }
th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
th { background: #fafafa; font-weight: 600; color: #555; }
td a { color: #7c83fd; cursor: pointer; }
.empty { color: #aaa; padding: 40px 0; text-align: center; }
</style>
