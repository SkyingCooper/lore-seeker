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
              <div class="mt-2 break-all text-base font-medium text-neutral-800">{{ userInfo?.id ?? auth.userId ?? '—' }}</div>
            </div>
            <div v-if="!auth.isGuest" class="rounded-2xl border border-[#e7dfd3] bg-white/75 p-4">
              <div class="text-xs uppercase tracking-[0.14em] text-neutral-400">{{ copy.username }}</div>
              <div class="mt-2 text-base font-medium text-neutral-800">{{ userInfo?.username || auth.username || '—' }}</div>
            </div>
            <div v-if="!auth.isGuest" class="rounded-2xl border border-[#e7dfd3] bg-white/75 p-4">
              <div class="text-xs uppercase tracking-[0.14em] text-neutral-400">{{ copy.email }}</div>
              <div class="mt-2 break-all text-base font-medium text-neutral-800">{{ userInfo?.email || '—' }}</div>
            </div>
            <div class="rounded-2xl border border-[#e7dfd3] bg-white/75 p-4">
              <div class="text-xs uppercase tracking-[0.14em] text-neutral-400">{{ copy.createdAt }}</div>
              <div class="mt-2 text-base font-medium text-neutral-800">{{ formatDate(userInfo?.created_at) }}</div>
            </div>
            <div v-if="!auth.isGuest" class="rounded-2xl border border-[#e7dfd3] bg-white/75 p-4">
              <div class="text-xs uppercase tracking-[0.14em] text-neutral-400">{{ copy.lastLogin }}</div>
              <div class="mt-2 text-base font-medium text-neutral-800">{{ formatDate(userInfo?.last_login_at) }}</div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
      <div class="rounded-[28px] border border-[#dfd7ca] bg-white/82 p-6 shadow-[0_18px_48px_rgba(148,131,105,0.08)]">
        <div class="text-xs uppercase tracking-[0.14em] text-neutral-400">{{ copy.tokenAccount }}</div>
        <div class="mt-3 text-3xl font-semibold text-neutral-900">{{ tokenBalance?.balance ?? 0 }}</div>
        <div class="mt-1 text-sm text-neutral-500">{{ copy.balanceHint }}</div>
        <div class="mt-5 space-y-3 text-sm">
          <div class="flex items-center justify-between rounded-2xl bg-[#f7f1e8] px-4 py-3">
            <span class="text-neutral-500">{{ copy.totalConsumed }}</span>
            <span class="font-semibold text-neutral-900">{{ tokenBalance?.total_consumed ?? 0 }}</span>
          </div>
          <div class="flex items-center justify-between rounded-2xl bg-[#f7f1e8] px-4 py-3">
            <span class="text-neutral-500">{{ copy.lastUpdated }}</span>
            <span class="font-semibold text-neutral-900">{{ formatDate(tokenBalance?.updated_at) }}</span>
          </div>
        </div>
      </div>

      <div class="rounded-[28px] border border-[#dfd7ca] bg-white/82 p-6 shadow-[0_18px_48px_rgba(148,131,105,0.08)]">
        <div class="mb-4 flex items-center justify-between gap-3">
          <div>
            <div class="text-xs uppercase tracking-[0.14em] text-neutral-400">{{ copy.tokenHistory }}</div>
            <div class="mt-1 text-xl font-semibold text-neutral-900">{{ copy.recentUsage }}</div>
          </div>
        </div>
        <div v-if="tokenLogs.length === 0" class="rounded-2xl border border-dashed border-[#e5ddd2] px-4 py-10 text-center text-sm text-neutral-400">
          {{ copy.noUsage }}
        </div>
        <div v-else class="space-y-3">
          <div v-for="item in tokenLogs" :key="item.id" class="rounded-2xl border border-[#e6ddd0] bg-[#fdfaf5] px-4 py-3">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="font-semibold text-neutral-900">{{ item.stage || 'unknown' }}</div>
              <div class="text-xs text-neutral-400">{{ formatDate(item.created_at) }}</div>
            </div>
            <div class="mt-2 grid gap-2 text-sm text-neutral-600 md:grid-cols-4">
              <div>{{ copy.provider }}: {{ item.provider || '—' }}</div>
              <div>{{ copy.model }}: {{ item.model || '—' }}</div>
              <div>{{ copy.inputTokens }}: {{ item.input_tokens ?? 0 }}</div>
              <div>{{ copy.outputTokens }}: {{ item.output_tokens ?? 0 }}</div>
            </div>
            <div class="mt-2 flex flex-wrap gap-3 text-xs text-neutral-500">
              <span>{{ copy.actualConsumed }}: {{ item.actual_consumed ?? 0 }}</span>
              <span>{{ copy.balanceAfter }}: {{ item.balance_after ?? 0 }}</span>
              <span v-if="item.task_id">{{ copy.task }} #{{ item.task_id }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { UserRound } from '@lucide/vue'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useLocaleStore } from '@/stores/locale'

const auth = useAuthStore()
const locale = useLocaleStore()

interface UserInfo {
  id: string
  username: string | null
  email: string | null
  avatar_url: string | null
  is_guest: boolean
  last_login_at: string | null
  created_at: string | null
}
interface TokenBalance {
  balance: number
  total_consumed: number
  updated_at: string | null
}

interface TokenLog {
  id: number
  task_id: string | null
  stage: string | null
  provider: string | null
  model: string | null
  input_tokens: number | null
  output_tokens: number | null
  actual_consumed: number | null
  balance_after: number | null
  created_at: string | null
}

const userInfo = ref<UserInfo | null>(null)
const tokenBalance = ref<TokenBalance | null>(null)
const tokenLogs = ref<TokenLog[]>([])

onMounted(async () => {
  try {
    const [meRes, balanceRes, logsRes] = await Promise.all([
      api.get<UserInfo>('/api/v1/users/me'),
      api.get<TokenBalance>('/api/v1/users/me/token-balance'),
      api.get<{ items: TokenLog[] }>('/api/v1/users/me/token-consumption'),
    ])
    userInfo.value = meRes.data
    tokenBalance.value = balanceRes.data
    tokenLogs.value = logsRes.data.items || []
  } catch {
    // 未登录时使用 store 本地数据
  }
})

const copy = computed(() =>
  locale.isChinese
    ? {
        section: '个人信息',
        title: '个人信息',
        subtitle: '查看当前工作区会话的身份状态和基础标识信息。',
        identity: '当前身份',
        accountType: '账号类型',
        identifier: '会话标识',
        username: '用户名',
        email: '邮箱',
        createdAt: '注册时间',
        lastLogin: '最近登录',
        tokenAccount: 'Token 账户',
        balanceHint: '当前账户可继续使用的 token 余额。',
        totalConsumed: '累计消耗',
        lastUpdated: '最近更新',
        tokenHistory: '消耗流水',
        recentUsage: '最近任务消耗',
        noUsage: '暂无 token 消耗记录。',
        provider: '提供商',
        model: '模型',
        inputTokens: '输入',
        outputTokens: '输出',
        actualConsumed: '实际消耗',
        balanceAfter: '余额',
        task: '任务',
        guest: '游客会话',
        member: '正式账号',
        notAvailable: '暂无',
      }
    : {
        section: 'Profile',
        title: 'Profile',
        subtitle: 'Review the current workspace identity and session metadata.',
        identity: 'Current identity',
        accountType: 'Account type',
        identifier: 'Session identifier',
        username: 'Username',
        email: 'Email',
        createdAt: 'Registered',
        lastLogin: 'Last login',
        tokenAccount: 'Token account',
        balanceHint: 'Remaining token balance for the current account.',
        totalConsumed: 'Total consumed',
        lastUpdated: 'Updated',
        tokenHistory: 'Consumption log',
        recentUsage: 'Recent task usage',
        noUsage: 'No token consumption records yet.',
        provider: 'Provider',
        model: 'Model',
        inputTokens: 'Input',
        outputTokens: 'Output',
        actualConsumed: 'Consumed',
        balanceAfter: 'Balance',
        task: 'Task',
        guest: 'Guest session',
        member: 'Member account',
        notAvailable: 'N/A',
      }
)

function formatDate(iso: string | null | undefined): string {
  if (!iso) return copy.value.notAvailable
  return new Date(iso).toLocaleString()
}

const displayName = computed(() => {
  if (auth.isGuest) return copy.value.guest
  return userInfo.value?.username || auth.username || auth.userId?.slice(0, 8) || 'member'
})
const accountType = computed(() => (auth.isGuest ? copy.value.guest : copy.value.member))
</script>
