<template>
  <div class="space-y-6">
    <header class="space-y-2">
      <div class="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-neutral-400">
        <CircleHelp :size="14" class="text-[#8ca0b5]" />
        <span>{{ copy.section }}</span>
      </div>
      <h1 class="text-4xl font-semibold tracking-tight text-neutral-900">{{ copy.title }}</h1>
      <p class="max-w-2xl text-sm leading-7 text-neutral-500">{{ copy.subtitle }}</p>
    </header>

    <div class="grid gap-4 lg:grid-cols-2">
      <section
        v-for="item in helpItems"
        :key="item.title"
        class="rounded-[26px] border border-[#dfd7ca] bg-white/82 p-5 shadow-[0_18px_48px_rgba(148,131,105,0.08)]"
      >
        <div class="flex items-start gap-4">
          <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[#f5efe6] text-[#6f8cab]">
            <component :is="item.icon" :size="20" />
          </div>
          <div>
            <h2 class="text-lg font-semibold text-neutral-900">{{ item.title }}</h2>
            <p class="mt-2 text-sm leading-7 text-neutral-500">{{ item.body }}</p>
            <n-button v-if="item.action" text type="primary" class="mt-3" @click="router.push(item.action.to)">
              {{ item.action.label }}
            </n-button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
// 文件说明：
// HelpView 提供当前已接入功能的操作入口，避免侧边栏帮助入口停留在占位提示。
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { NButton } from 'naive-ui'
import { BookOpenText, CircleHelp, MessageCircleMore, Search, Settings2, SquarePen } from '@lucide/vue'
import { useLocaleStore } from '@/stores/locale'

const router = useRouter()
const locale = useLocaleStore()

const copy = computed(() =>
  locale.isChinese
    ? {
        section: '帮助',
        title: '帮助',
        subtitle: '快速了解当前工作台已接入的核心能力。',
        startTask: '创建搜索任务',
        startTaskBody: '在任务页填写主题、关键词、搜索模式和来源网站，提交后可以手动启动执行。',
        askKnowledge: '知识库问答',
        askKnowledgeBody: '在对话页向已生成报告提问，系统会检索当前用户自己的知识切片并返回引用。',
        readReports: '阅读报告',
        readReportsBody: '在报告库查看已生成的 Markdown 报告，支持目录导航和正文阅读。',
        settings: '管理主题和偏好',
        settingsBody: '在设置页维护关注主题和 Agent 偏好 JSON。',
        open: '打开',
      }
    : {
        section: 'Help',
        title: 'Help',
        subtitle: 'A quick guide to the workspace features currently wired to the backend.',
        startTask: 'Create a search task',
        startTaskBody: 'Use the task page to set topic, keywords, search mode, and source sites, then start the run manually.',
        askKnowledge: 'Ask the knowledge base',
        askKnowledgeBody: 'Use chat to query generated reports. Retrieval is isolated to the current user.',
        readReports: 'Read reports',
        readReportsBody: 'Browse generated Markdown reports with table-of-contents navigation.',
        settings: 'Manage topics and preferences',
        settingsBody: 'Maintain tracked topics and Agent preference JSON in settings.',
        open: 'Open',
      }
)

const helpItems = computed(() => [
  { title: copy.value.startTask, body: copy.value.startTaskBody, icon: SquarePen, action: { label: copy.value.open, to: '/tasks/new' } },
  { title: copy.value.askKnowledge, body: copy.value.askKnowledgeBody, icon: MessageCircleMore, action: { label: copy.value.open, to: '/chat' } },
  { title: copy.value.readReports, body: copy.value.readReportsBody, icon: BookOpenText, action: { label: copy.value.open, to: '/reports' } },
  { title: copy.value.settings, body: copy.value.settingsBody, icon: Settings2, action: { label: copy.value.open, to: '/settings' } },
])
</script>
