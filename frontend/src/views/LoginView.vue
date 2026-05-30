<template>
  <div class="grid min-h-screen bg-[var(--ls-bg)] lg:grid-cols-[1.1fr_0.9fr]">
    <section class="hidden border-r border-[#e6ddd0] bg-[linear-gradient(180deg,#faf4ea_0%,#f4ecdf_100%)] px-12 py-14 lg:flex lg:flex-col">
      <img :src="logoFull" alt="Lore Seeker" class="h-auto w-[360px] max-w-full" />
      <div class="mt-10 max-w-xl">
        <h1 class="text-5xl font-semibold tracking-tight text-neutral-900">{{ copy.heroTitle }}</h1>
        <p class="mt-6 text-lg leading-8 text-neutral-500">
          {{ copy.heroBody }}
        </p>
      </div>
      <div class="mt-auto grid gap-3 text-sm text-neutral-500">
        <div class="flex items-start gap-3 rounded-2xl border border-white/70 bg-white/85 px-4 py-4 shadow-[0_12px_32px_rgba(148,131,105,0.08)]">
          <div class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#eef3f8] text-[#607c99]">
            <SearchCheck :size="18" />
          </div>
          <div>{{ copy.heroPointA }}</div>
        </div>
        <div class="flex items-start gap-3 rounded-2xl border border-white/70 bg-white/85 px-4 py-4 shadow-[0_12px_32px_rgba(148,131,105,0.08)]">
          <div class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#f5efe5] text-[#b0884a]">
            <BookOpenText :size="18" />
          </div>
          <div>{{ copy.heroPointB }}</div>
        </div>
      </div>
    </section>

    <section class="flex items-center justify-center px-6 py-10 lg:px-12">
      <n-card class="w-full max-w-md rounded-[30px] border border-[#e2d8ca] shadow-[0_24px_64px_rgba(148,131,105,0.12)]" :bordered="false">
        <div class="mb-6">
          <div class="text-xs uppercase tracking-[0.18em] text-neutral-400">{{ copy.account }}</div>
          <h2 class="mt-2 text-3xl font-semibold text-neutral-900">{{ mode === 'login' ? copy.login : copy.register }}</h2>
          <p class="mt-2 text-sm leading-6 text-neutral-500">
            {{ mode === 'login' ? copy.loginHint : copy.registerHint }}
          </p>
        </div>

        <div class="mb-5 grid grid-cols-2 gap-2 rounded-2xl bg-[#f4ede3] p-1.5">
          <button
            class="rounded-xl px-3 py-2.5 text-sm font-medium transition"
            :class="mode === 'login' ? 'bg-white text-neutral-900 shadow-[0_10px_28px_rgba(148,131,105,0.12)]' : 'text-neutral-500'"
            @click="mode = 'login'"
          >
            {{ copy.login }}
          </button>
          <button
            class="rounded-xl px-3 py-2.5 text-sm font-medium transition"
            :class="mode === 'register' ? 'bg-white text-neutral-900 shadow-[0_10px_28px_rgba(148,131,105,0.12)]' : 'text-neutral-500'"
            @click="mode = 'register'"
          >
            {{ copy.register }}
          </button>
        </div>

        <div class="space-y-4">
          <div class="space-y-2">
            <label class="text-sm font-medium text-neutral-700">{{ copy.email }}</label>
            <n-input v-model:value="email" type="text" placeholder="name@example.com" size="large">
              <template #prefix>
                <Mail :size="16" class="text-[#93a4b6]" />
              </template>
            </n-input>
          </div>

          <div class="space-y-2">
            <label class="text-sm font-medium text-neutral-700">{{ copy.password }}</label>
            <n-input v-model:value="password" type="password" show-password-on="click" :placeholder="copy.passwordPlaceholder" size="large">
              <template #prefix>
                <KeyRound :size="16" class="text-[#93a4b6]" />
              </template>
            </n-input>
          </div>

          <n-alert v-if="error" type="error" :show-icon="false">{{ error }}</n-alert>

          <div class="grid gap-3 pt-2">
            <n-button type="primary" size="large" :loading="loading" @click="submit">
              <template #icon>
                <LogIn :size="18" />
              </template>
              {{ mode === 'login' ? copy.enterLogin : copy.enterRegister }}
            </n-button>
            <n-button quaternary size="large" @click="continueAsGuest">
              <template #icon>
                <WandSparkles :size="18" />
              </template>
              {{ copy.guestContinue }}
            </n-button>
          </div>
        </div>
      </n-card>
    </section>
  </div>
</template>

<script setup lang="ts">
// 文件说明：
// LoginView 提供注册、登录和游客继续三种入口，是前端品牌感和第一印象最强的页面之一。
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NAlert, NButton, NCard, NInput } from 'naive-ui'
import { BookOpenText, KeyRound, LogIn, Mail, SearchCheck, WandSparkles } from '@lucide/vue'
import logoFull from '@/assets/logo-word.avif'
import { useAuthStore } from '@/stores/auth'
import { useLocaleStore } from '@/stores/locale'

const auth = useAuthStore()
const locale = useLocaleStore()
const router = useRouter()
const mode = ref<'login' | 'register'>('login')
const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

const copy = computed(() =>
  locale.isChinese
    ? {
        heroTitle: '构建一个可持续演化的知识工作区。',
        heroBody: '用多 Agent 搜索、整理、入库和检索主题知识，让报告与记忆在同一个工作流里持续积累。',
        heroPointA: 'Search, organize, retrieve. 一次搜索，持续演化成可问答的知识库。',
        heroPointB: '适合专题调研、长期追踪和个人知识资产沉淀。',
        account: '账户',
        login: '登录',
        register: '注册',
        loginHint: '继续你的搜索与知识整理工作。',
        registerHint: '创建账号，保存长期知识库和偏好。',
        email: '邮箱',
        password: '密码',
        passwordPlaceholder: '至少 8 位，包含字母和数字',
        enterLogin: '登录并进入工作台',
        enterRegister: '注册并进入工作台',
        guestContinue: '以游客身份继续',
      }
    : {
        heroTitle: 'Build a durable knowledge workspace.',
        heroBody: 'Use multiple agents to search, organize, store, and retrieve topic knowledge in one continuous workflow.',
        heroPointA: 'Search, organize, retrieve. One search can evolve into a long-lived knowledge base.',
        heroPointB: 'Ideal for topic research, long-term tracking, and personal knowledge assets.',
        account: 'Account',
        login: 'Login',
        register: 'Register',
        loginHint: 'Return to your research and knowledge workflows.',
        registerHint: 'Create an account to save long-lived knowledge and preferences.',
        email: 'Email',
        password: 'Password',
        passwordPlaceholder: 'At least 8 characters with letters and digits',
        enterLogin: 'Login and enter workspace',
        enterRegister: 'Register and enter workspace',
        guestContinue: 'Continue as guest',
      }
)

async function submit() {
  loading.value = true
  error.value = ''
  try {
    if (mode.value === 'login') {
      await auth.login(email.value, password.value)
    } else {
      await auth.register(email.value, password.value)
    }
    router.push('/browse')
  } catch (e: any) {
    error.value = e.response?.data?.detail || '操作失败'
  } finally {
    loading.value = false
  }
}

async function continueAsGuest() {
  await auth.guestLogin()
  router.push('/browse')
}
</script>
