<template>
  <div class="space-y-6">
    <header class="space-y-2">
      <div class="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-neutral-400">
        <Users :size="14" class="text-[#8ca0b5]" />
        <span>{{ copy.section }}</span>
      </div>
      <h1 class="text-4xl font-semibold tracking-tight text-neutral-900">{{ copy.title }}</h1>
      <p class="max-w-2xl text-sm leading-7 text-neutral-500">{{ copy.subtitle }}</p>
    </header>

    <section class="rounded-[28px] border border-[#dfd7ca] bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(255,251,245,0.96))] p-7 shadow-[0_18px_48px_rgba(148,131,105,0.08)]">
      <div class="flex items-start gap-4">
        <div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-[#eef4fb] text-[#5d7896]">
          <Users :size="26" />
        </div>
        <div>
          <h2 class="text-xl font-semibold text-neutral-900">{{ copy.cardTitle }}</h2>
          <p class="mt-2 max-w-2xl text-sm leading-7 text-neutral-500">{{ copy.cardBody }}</p>
          <n-button secondary class="mt-4 rounded-2xl" @click="router.push('/profile')">
            {{ copy.profile }}
          </n-button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
// 文件说明：
// CommunityView 承接账户弹窗中的协作社区入口。当前后端还没有团队/协作表，
// 前端先提供稳定路由和功能说明，不再停留在菜单 toast。
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { NButton } from 'naive-ui'
import { Users } from '@lucide/vue'
import { useLocaleStore } from '@/stores/locale'

const router = useRouter()
const locale = useLocaleStore()

const copy = computed(() =>
  locale.isChinese
    ? {
        section: '协作社区',
        title: '协作社区',
        subtitle: '未来这里会承载团队知识空间、共享报告和协作成员管理。',
        cardTitle: '协作空间准备中',
        cardBody: '当前系统以个人知识库为主，后续接入团队与共享数据模型后，这里会显示成员、空间和共享报告。',
        profile: '查看个人信息',
      }
    : {
        section: 'Community',
        title: 'Community',
        subtitle: 'This area will host team spaces, shared reports, and collaboration members.',
        cardTitle: 'Collaboration workspace is being prepared',
        cardBody: 'The current system focuses on personal knowledge. Once team and sharing models are added, members, spaces, and shared reports will appear here.',
        profile: 'View profile',
      }
)
</script>
