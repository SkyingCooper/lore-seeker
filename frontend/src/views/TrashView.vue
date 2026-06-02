<template>
  <div class="space-y-6">
    <header class="space-y-2">
      <div class="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-neutral-400">
        <Trash2 :size="14" class="text-[#8ca0b5]" />
        <span>{{ copy.section }}</span>
      </div>
      <h1 class="text-4xl font-semibold tracking-tight text-neutral-900">{{ copy.title }}</h1>
      <p class="max-w-2xl text-sm leading-7 text-neutral-500">{{ copy.subtitle }}</p>
    </header>

    <section class="rounded-[28px] border border-[#dfd7ca] bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(255,251,245,0.96))] p-7 shadow-[0_18px_48px_rgba(148,131,105,0.08)]">
      <n-empty :description="copy.empty" class="py-10">
        <template #icon>
          <div class="flex h-16 w-16 items-center justify-center rounded-[22px] bg-[#f7efe5] text-[#8c7d6e]">
            <Trash2 :size="28" />
          </div>
        </template>
      </n-empty>
      <div class="mt-4 flex justify-center">
        <n-button secondary class="rounded-2xl" @click="router.push('/tasks')">
          {{ copy.backTasks }}
        </n-button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
// 文件说明：
// TrashView 提供垃圾箱路由入口。当前后端任务列表默认过滤 deleted_at，
// 还没有恢复接口，因此页面先明确展示空状态和返回任务页的路径。
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NEmpty } from 'naive-ui'
import { Trash2 } from '@lucide/vue'
import { useLocaleStore } from '@/stores/locale'

const router = useRouter()
const locale = useLocaleStore()

const copy = computed(() =>
  locale.isChinese
    ? {
        section: '垃圾箱',
        title: '垃圾箱',
        subtitle: '这里用于承接已删除任务和内容的回收站视图。',
        empty: '当前没有可恢复的内容。',
        backTasks: '返回任务列表',
      }
    : {
        section: 'Trash',
        title: 'Trash',
        subtitle: 'Deleted tasks and content will be collected here.',
        empty: 'No recoverable content right now.',
        backTasks: 'Back to tasks',
      }
)
</script>
