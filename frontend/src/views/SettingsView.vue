<template>
  <div class="settings">
    <h2>设置</h2>

    <section>
      <h3>关注主题</h3>
      <div v-for="t in topics" :key="t.id" class="topic-item">
        <strong>{{ t.name }}</strong>
        <span>{{ t.target_sites?.join(', ') }}</span>
      </div>
      <div class="new-topic">
        <input v-model="newTopic.name" placeholder="主题名称" />
        <input v-model="newTopic.description" placeholder="描述（可选）" />
        <input v-model="sitesInput" placeholder="目标网站（逗号分隔）" />
        <select v-model="newTopic.search_mode">
          <option value="api">API 搜索</option>
          <option value="crawl">爬虫扫描</option>
          <option value="both">混合</option>
        </select>
        <button @click="addTopic">添加主题</button>
      </div>
    </section>

    <section>
      <h3>个性化偏好（Agent 总结）</h3>
      <textarea v-model="prefsText" rows="6" />
      <button @click="savePrefs">保存偏好</button>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const topics = ref<any[]>([])
const newTopic = ref({ name: '', description: '', search_mode: 'api', target_sites: [] as string[] })
const sitesInput = ref('')
const prefsText = ref('')

onMounted(async () => {
  const [topicsRes, meRes] = await Promise.all([
    api.get('/api/v1/search/topics'),
    api.get('/api/v1/users/me'),
  ])
  topics.value = topicsRes.data
  prefsText.value = JSON.stringify(meRes.data.preferences, null, 2)
})

async function addTopic() {
  newTopic.value.target_sites = sitesInput.value.split(',').map(s => s.trim()).filter(Boolean)
  await api.post('/api/v1/search/topics', newTopic.value)
  const res = await api.get('/api/v1/search/topics')
  topics.value = res.data
  newTopic.value = { name: '', description: '', search_mode: 'api', target_sites: [] }
  sitesInput.value = ''
}

async function savePrefs() {
  try {
    const prefs = JSON.parse(prefsText.value)
    await api.patch('/api/v1/users/me/preferences', { preferences: prefs })
  } catch {
    alert('JSON 格式错误')
  }
}
</script>

<style scoped>
.settings { padding: 32px; max-width: 700px; }
h2 { margin-bottom: 24px; }
section { background: #fff; border-radius: 10px; padding: 24px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,.06); }
h3 { margin: 0 0 16px; font-size: 15px; }
.topic-item { padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 14px; display: flex; gap: 12px; }
.new-topic { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
.new-topic input, .new-topic select { padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; }
.new-topic button, section > button { padding: 8px 16px; background: #7c83fd; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-family: monospace; font-size: 13px; box-sizing: border-box; margin-bottom: 10px; }
</style>
