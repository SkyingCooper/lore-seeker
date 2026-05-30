<template>
  <div class="space-y-6">
    <header class="space-y-2">
      <div class="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-neutral-400">
        <MessageCircleMore :size="14" class="text-[#8ca0b5]" />
        <span>{{ copy.section }}</span>
      </div>
      <h1 class="text-4xl font-semibold tracking-tight text-neutral-900">{{ copy.title }}</h1>
      <p class="max-w-2xl text-sm leading-7 text-neutral-500">{{ copy.subtitle }}</p>
    </header>

    <section class="rounded-[28px] border border-[#dfd7ca] bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(255,251,245,0.96))] p-7 shadow-[0_18px_48px_rgba(148,131,105,0.08)]">
      <div class="flex items-start gap-4">
        <div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-[#eef4fb] text-[#5d7896]">
          <Bot :size="24" />
        </div>
        <div>
          <h2 class="text-xl font-semibold text-neutral-900">{{ copy.cardTitle }}</h2>
          <p class="mt-2 max-w-2xl text-sm leading-7 text-neutral-500">{{ copy.cardBody }}</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
// 文件说明：
// ChatView 作为与 Lore Seeker 对话的独立工作区入口，当前先提供结构化占位页面。
// 后续这里会承接会话线程、上下文面板和与知识库联动的问答体验。
import { computed } from 'vue'
import { Bot, MessageCircleMore } from '@lucide/vue'
import { useLocaleStore } from '@/stores/locale'

const locale = useLocaleStore()

const copy = computed(() =>
  locale.isChinese
    ? {
        section: '对话',
        title: '与 Lore Seeker 对话',
        subtitle: '在这里直接发起研究问答、追问现有报告，或围绕知识库持续展开对话。',
        cardTitle: '对话工作区准备中',
        cardBody: '当前先补齐导航与页面骨架，后续会把会话列表、上下文引用和问答输入区接到这里。',
      }
    : {
        section: 'Conversation',
        title: 'Talk with Lore Seeker',
        subtitle: 'Start research questions, follow up on reports, and continue long-lived knowledge conversations here.',
        cardTitle: 'Conversation workspace is being prepared',
        cardBody: 'This page currently provides the route and shell. Thread history, context references, and the chat composer will land here next.',
      }
)
</script>
