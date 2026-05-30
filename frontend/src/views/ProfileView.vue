<template>
  <div class="space-y-6">
    <header class="space-y-2">
      <div class="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-neutral-400">
        <UserRound :size="14" class="text-[#8ca0b5]" />
        <span>{{ copy.section }}</span>
      </div>
      <h1 class="text-4xl font-semibold tracking-tight text-neutral-900">{{ copy.title }}</h1>
      <p class="max-w-2xl text-sm leading-7 text-neutral-500">{{ copy.subtitle }}</p>
    </header>

    <section class="rounded-[28px] border border-[#dfd7ca] bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(255,251,245,0.96))] p-7 shadow-[0_18px_48px_rgba(148,131,105,0.08)]">
      <div class="flex flex-col gap-6 lg:flex-row lg:items-start">
        <div class="flex h-20 w-20 items-center justify-center rounded-[28px] bg-[#eef4fb] text-[#5d7896]">
          <UserRound :size="34" />
        </div>
        <div class="min-w-0 flex-1 space-y-5">
          <div>
            <div class="text-sm text-neutral-400">{{ copy.identity }}</div>
            <div class="mt-1 text-2xl font-semibold text-neutral-900">{{ displayName }}</div>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <div class="rounded-2xl border border-[#e7dfd3] bg-white/75 p-4">
              <div class="text-xs uppercase tracking-[0.14em] text-neutral-400">{{ copy.accountType }}</div>
              <div class="mt-2 text-base font-medium text-neutral-800">{{ accountType }}</div>
            </div>
            <div class="rounded-2xl border border-[#e7dfd3] bg-white/75 p-4">
              <div class="text-xs uppercase tracking-[0.14em] text-neutral-400">{{ copy.identifier }}</div>
              <div class="mt-2 break-all text-base font-medium text-neutral-800">{{ auth.userId ?? 'guest' }}</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
// 文件说明：
// ProfileView 用于展示当前会话的基础身份信息，承接左上角账户下拉中的“个人信息”入口。
// 当前先展示本地可得的账号类型和标识，后续可扩展为完整资料页。
import { computed } from 'vue'
import { UserRound } from '@lucide/vue'
import { useAuthStore } from '@/stores/auth'
import { useLocaleStore } from '@/stores/locale'

const auth = useAuthStore()
const locale = useLocaleStore()

const copy = computed(() =>
  locale.isChinese
    ? {
        section: '个人信息',
        title: '个人信息',
        subtitle: '查看当前工作区会话的身份状态和基础标识信息。',
        identity: '当前身份',
        accountType: '账号类型',
        identifier: '会话标识',
        guest: '游客会话',
        member: '正式账号',
      }
    : {
        section: 'Profile',
        title: 'Profile',
        subtitle: 'Review the current workspace identity and session metadata.',
        identity: 'Current identity',
        accountType: 'Account type',
        identifier: 'Session identifier',
        guest: 'Guest session',
        member: 'Member account',
      }
)

const displayName = computed(() => (auth.isGuest ? copy.value.guest : auth.userId?.slice(0, 8) ?? 'member'))
const accountType = computed(() => (auth.isGuest ? copy.value.guest : copy.value.member))
</script>
