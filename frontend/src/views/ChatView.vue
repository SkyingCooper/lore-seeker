<template>
  <div class="grid min-h-[calc(100vh-4rem)] gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
    <section class="flex min-h-[640px] flex-col overflow-hidden rounded-[28px] border border-[#dfd7ca] bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(255,251,245,0.98))] shadow-[0_18px_48px_rgba(148,131,105,0.08)]">
      <header class="border-b border-[#e8dfd2] px-6 py-5">
        <div class="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-neutral-400">
          <MessageCircleMore :size="14" class="text-[#8ca0b5]" />
          <span>{{ copy.section }}</span>
        </div>
        <h1 class="mt-2 text-3xl font-semibold tracking-tight text-neutral-900">{{ copy.title }}</h1>
        <p class="mt-2 max-w-2xl text-sm leading-6 text-neutral-500">{{ copy.subtitle }}</p>
      </header>

      <div ref="scrollBox" class="flex-1 space-y-4 overflow-y-auto px-5 py-5">
        <div
          v-for="messageItem in messages"
          :key="messageItem.id"
          class="flex"
          :class="messageItem.role === 'user' ? 'justify-end' : 'justify-start'"
        >
          <div
            class="max-w-[82%] rounded-[24px] px-4 py-3 text-sm leading-7 shadow-[0_10px_28px_rgba(120,105,88,0.08)]"
            :class="messageItem.role === 'user' ? 'bg-[#4f6682] text-white' : 'border border-[#e5dccf] bg-white/88 text-[#34404c]'"
          >
            <div class="whitespace-pre-wrap">{{ messageItem.content }}</div>
            <div v-if="messageItem.sources?.length" class="mt-3 space-y-2 border-t border-[#ece3d6] pt-3">
              <button
                v-for="source in messageItem.sources"
                :key="`${messageItem.id}-${source.report_id}-${source.score}`"
                class="block w-full rounded-2xl bg-[#f8f3eb] px-3 py-2 text-left text-xs leading-5 text-[#596776] transition hover:bg-[#f2eadf]"
                @click="router.push(`/browse/${source.report_id}`)"
              >
                <div class="font-semibold text-[#334e6b]">{{ copy.report }} #{{ source.report_id }}</div>
                <div class="mt-1 line-clamp-2">{{ source.content }}</div>
              </button>
            </div>
          </div>
        </div>

        <n-empty v-if="messages.length === 0" :description="copy.empty" class="py-20">
          <template #icon>
            <div class="flex h-16 w-16 items-center justify-center rounded-[22px] bg-[#eef4fb] text-[#5d7896]">
              <Bot :size="30" />
            </div>
          </template>
        </n-empty>
      </div>

      <footer class="border-t border-[#e8dfd2] bg-[#fffaf3] px-5 py-4">
        <div class="flex gap-3">
          <n-input
            v-model:value="query"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 4 }"
            :placeholder="copy.placeholder"
            :disabled="loading"
            @keydown.enter.exact.prevent="send"
          />
          <n-button type="primary" size="large" class="shrink-0 rounded-2xl" :loading="loading" @click="send">
            <template #icon>
              <SendHorizontal :size="18" />
            </template>
            {{ copy.send }}
          </n-button>
        </div>
      </footer>
    </section>

    <aside class="space-y-4">
      <section class="rounded-[26px] border border-[#dfd7ca] bg-white/78 p-5 shadow-[0_18px_48px_rgba(148,131,105,0.08)]">
        <div class="flex items-center gap-3">
          <div class="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#f5efe6] text-[#6f8cab]">
            <BookOpenText :size="20" />
          </div>
          <div>
            <div class="text-base font-semibold text-neutral-900">{{ copy.knowledgeTitle }}</div>
            <div class="text-xs text-neutral-500">{{ copy.knowledgeHint }}</div>
          </div>
        </div>
      </section>

      <section class="rounded-[26px] border border-[#dfd7ca] bg-white/78 p-5 shadow-[0_18px_48px_rgba(148,131,105,0.08)]">
        <div class="mb-3 text-sm font-semibold text-neutral-800">{{ copy.examples }}</div>
        <div class="space-y-2">
          <button
            v-for="example in copy.exampleItems"
            :key="example"
            class="w-full rounded-2xl bg-[#f8f3eb] px-3 py-2 text-left text-sm leading-6 text-[#596776] transition hover:bg-[#f0e7d9]"
            @click="query = example"
          >
            {{ example }}
          </button>
        </div>
      </section>
    </aside>
  </div>
</template>

<script setup lang="ts">
// 文件说明：
// ChatView 接入 /api/v1/knowledge/query，用于围绕当前用户知识库进行问答。
// 游客没有知识检索权限，接口会引导到登录页；已登录用户可查看回答和引用来源。
import { computed, nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NEmpty, NInput, useMessage } from 'naive-ui'
import { BookOpenText, Bot, MessageCircleMore, SendHorizontal } from '@lucide/vue'
import api from '@/api/client'
import { useLocaleStore } from '@/stores/locale'

interface SourceItem {
  content: string
  report_id: string
  score?: number | null
}

interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  sources?: SourceItem[]
}

const router = useRouter()
const locale = useLocaleStore()
const message = useMessage()
const query = ref('')
const loading = ref(false)
const messages = ref<ChatMessage[]>([])
const scrollBox = ref<HTMLElement | null>(null)
let nextId = 1

const copy = computed(() =>
  locale.isChinese
    ? {
        section: '对话',
        title: '与 Lore Seeker 对话',
        subtitle: '直接向自己的知识库提问，回答会基于已生成报告和知识切片，并返回引用来源。',
        empty: '输入一个问题，开始检索你的知识库。',
        placeholder: '问问你的知识库...',
        send: '发送',
        report: '报告',
        knowledgeTitle: '知识库问答',
        knowledgeHint: '基于当前用户的报告与切片，已做用户隔离。',
        examples: '示例问题',
        exampleItems: ['最近的报告里有哪些关键结论？', '帮我总结一下 AI 安全相关内容', '哪些资料提到了工程实践？'],
        emptyQuery: '请输入问题',
        failed: '问答失败，请稍后重试',
      }
    : {
        section: 'Conversation',
        title: 'Talk with Lore Seeker',
        subtitle: 'Ask your knowledge base directly. Answers are grounded in generated reports and return source references.',
        empty: 'Ask a question to start searching your knowledge base.',
        placeholder: 'Ask your knowledge base...',
        send: 'Send',
        report: 'Report',
        knowledgeTitle: 'Knowledge Q&A',
        knowledgeHint: 'Uses only your reports and chunks with user isolation.',
        examples: 'Examples',
        exampleItems: ['What are the key findings in recent reports?', 'Summarize AI safety content', 'Which sources mention engineering practice?'],
        emptyQuery: 'Please enter a question',
        failed: 'Failed to answer. Please try again.',
      }
)

async function send() {
  const text = query.value.trim()
  if (!text) {
    message.warning(copy.value.emptyQuery)
    return
  }

  messages.value.push({ id: nextId++, role: 'user', content: text })
  query.value = ''
  loading.value = true
  await scrollToBottom()

  try {
    const res = await api.post('/api/v1/knowledge/query', {
      query: text,
      top_k: 5,
    })
    messages.value.push({
      id: nextId++,
      role: 'assistant',
      content: res.data.answer,
      sources: res.data.sources || [],
    })
  } catch {
    message.error(copy.value.failed)
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

async function scrollToBottom() {
  await nextTick()
  if (scrollBox.value) {
    scrollBox.value.scrollTop = scrollBox.value.scrollHeight
  }
}
</script>
