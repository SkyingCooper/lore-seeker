<template>
  <div class="space-y-6">
    <header class="space-y-2">
      <div class="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-neutral-400">
        <Inbox :size="14" class="text-[#8ca0b5]" />
        <span>{{ copy.section }}</span>
      </div>
      <h1 class="text-4xl font-semibold tracking-tight text-neutral-900">{{ copy.title }}</h1>
      <p class="max-w-2xl text-sm leading-7 text-neutral-500">{{ copy.subtitle }}</p>
    </header>

    <section class="rounded-[28px] border border-[#dfd7ca] bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(255,251,245,0.96))] p-7 shadow-[0_18px_48px_rgba(148,131,105,0.08)]">
      <n-empty :description="copy.empty" class="py-10">
        <template #icon>
          <div class="flex h-16 w-16 items-center justify-center rounded-[22px] bg-[#f7efe5] text-[#7b92ab]">
            <Inbox :size="28" />
          </div>
        </template>
      </n-empty>
    </section>
  </div>
</template>

<script setup lang="ts">
// 文件说明：
// InboxView 作为消息与系统通知入口，当前用于承接侧栏工具栏中的“收件箱”动作。
// 后续可在这里接搜索任务通知、报告完成提醒和系统级消息流。
import { computed } from 'vue'
import { NEmpty } from 'naive-ui'
import { Inbox } from '@lucide/vue'
import { useLocaleStore } from '@/stores/locale'

const locale = useLocaleStore()

const copy = computed(() =>
  locale.isChinese
    ? {
        section: '收件箱',
        title: '收件箱',
        subtitle: '集中查看任务完成提醒、系统消息和与你的知识工作流相关的通知。',
        empty: '暂时没有新的通知。',
      }
    : {
        section: 'Inbox',
        title: 'Inbox',
        subtitle: 'Review task completions, system messages, and workflow notifications in one place.',
        empty: 'No new notifications yet.',
      }
)
</script>
