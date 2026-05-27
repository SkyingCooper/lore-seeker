<template>
  <div class="report-view" v-if="report">
    <aside class="toc">
      <div class="toc-title">目录</div>
      <ul>
        <li
          v-for="item in report.toc"
          :key="item.anchor"
          :class="`level-${item.level}`"
          @click="scrollTo(item.anchor)"
        >
          {{ item.title }}
        </li>
      </ul>
    </aside>
    <article class="content">
      <MdPreview :modelValue="report.content_md" theme="light" codeTheme="github" />
    </article>
  </div>
  <div v-else class="loading">加载中...</div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { MdPreview } from 'md-editor-v3'
import api from '@/api/client'

const route = useRoute()
const report = ref<any>(null)

onMounted(async () => {
  const res = await api.get(`/api/v1/reports/${route.params.reportId}`)
  report.value = res.data
})

function scrollTo(anchor: string) {
  const el = document.getElementById(anchor)
  el?.scrollIntoView({ behavior: 'smooth' })
}
</script>

<style scoped>
.report-view { display: flex; height: 100vh; }
.toc {
  width: 240px; min-width: 200px; padding: 24px 16px; overflow-y: auto;
  border-right: 1px solid #e8e8e8; background: #fafafa; position: sticky; top: 0; height: 100vh;
}
.toc-title { font-weight: 600; font-size: 13px; color: #888; text-transform: uppercase; margin-bottom: 12px; }
.toc ul { list-style: none; padding: 0; margin: 0; }
.toc li { padding: 5px 8px; cursor: pointer; font-size: 13px; border-radius: 4px; color: #444; }
.toc li:hover { background: #efefef; }
.toc li.level-2 { font-weight: 600; }
.toc li.level-3 { padding-left: 20px; color: #666; }
.content { flex: 1; padding: 32px 48px; overflow-y: auto; max-width: 860px; }
.loading { padding: 60px; text-align: center; color: #aaa; }
</style>
