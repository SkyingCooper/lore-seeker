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

    <section class="grid gap-4 lg:grid-cols-2">
      <button
        v-for="item in entries"
        :key="item.title"
        class="rounded-[28px] border border-[#dfd7ca] bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(255,251,245,0.96))] p-6 text-left shadow-[0_18px_48px_rgba(148,131,105,0.08)] transition hover:-translate-y-0.5 hover:shadow-[0_22px_56px_rgba(148,131,105,0.12)]"
        @click="router.push(item.to)"
      >
        <div class="flex items-start gap-4">
          <div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-[#eef4fb] text-[#5d7896]">
            <component :is="item.icon" :size="24" />
          </div>
          <div>
            <h2 class="text-xl font-semibold text-neutral-900">{{ item.title }}</h2>
            <p class="mt-2 max-w-2xl text-sm leading-7 text-neutral-500">{{ item.body }}</p>
          </div>
        </div>
      </button>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { BookOpenText, MessageCircleMore, Settings2, UserRound, Users } from '@lucide/vue'
import { useLocaleStore } from '@/stores/locale'

const router = useRouter()
const locale = useLocaleStore()

const copy = computed(() =>
  locale.isChinese
    ? {
        section: '协作社区',
        title: '协作社区',
        subtitle: '这里集中放置账号、报告、问答和配置入口，作为当前工作台的协作导航页。',
        profileTitle: '个人信息',
        profileBody: '查看当前身份、账号信息、token 余额和最近消耗流水。',
        reportsTitle: '报告归档',
        reportsBody: '统一查看历史报告、质量分和评估结果。',
        chatTitle: '知识问答',
        chatBody: '进入知识库问答，围绕报告与切片进行检索式对话。',
        settingsTitle: '个人设置',
        settingsBody: '维护关注主题、用户偏好和研究配置。',
      }
    : {
        section: 'Community',
        title: 'Community',
        subtitle: 'A collaboration-style hub for account, reports, Q&A, and configuration routes in the current workspace.',
        profileTitle: 'Profile',
        profileBody: 'Review identity, account details, token balance, and recent consumption logs.',
        reportsTitle: 'Report archive',
        reportsBody: 'Browse historical reports, quality scores, and feedback.',
        chatTitle: 'Knowledge chat',
        chatBody: 'Open retrieval-based conversations grounded in reports and chunks.',
        settingsTitle: 'Settings',
        settingsBody: 'Maintain tracked topics, user preferences, and research configuration.',
      }
)

const entries = computed(() => [
  { title: copy.value.profileTitle, body: copy.value.profileBody, icon: UserRound, to: '/profile' },
  { title: copy.value.reportsTitle, body: copy.value.reportsBody, icon: BookOpenText, to: '/reports' },
  { title: copy.value.chatTitle, body: copy.value.chatBody, icon: MessageCircleMore, to: '/chat' },
  { title: copy.value.settingsTitle, body: copy.value.settingsBody, icon: Settings2, to: '/settings' },
])
</script>
