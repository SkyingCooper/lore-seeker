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
          <h2 class="mt-2 text-3xl font-semibold text-neutral-900">{{ modeLabel }}</h2>
          <p class="mt-2 text-sm leading-6 text-neutral-500">
            {{ modeHint }}
          </p>
        </div>

        <div class="mb-5 grid grid-cols-2 rounded-2xl bg-[#f4ede3] p-1.5">
          <button
            class="rounded-xl px-3 py-2.5 text-sm font-medium transition"
            :class="mode === 'login' ? 'bg-white text-neutral-900 shadow-[0_10px_28px_rgba(148,131,105,0.12)]' : 'text-neutral-500'"
            @click="switchMode('login')"
          >
            {{ copy.login }}
          </button>
          <button
            class="rounded-xl px-3 py-2.5 text-sm font-medium transition"
            :class="mode === 'register' ? 'bg-white text-neutral-900 shadow-[0_10px_28px_rgba(148,131,105,0.12)]' : 'text-neutral-500'"
            @click="switchMode('register')"
          >
            {{ copy.register }}
          </button>
        </div>

        <div class="space-y-4">
          <div v-if="mode === 'register'" class="space-y-1.5">
            <label class="text-sm font-medium text-neutral-700">{{ copy.username }}</label>
            <n-input v-model:value="username" type="text" :placeholder="copy.usernamePlaceholder" size="large">
              <template #prefix>
                <UserRound :size="16" class="text-[#93a4b6]" />
              </template>
            </n-input>
          </div>

          <div class="space-y-1.5">
            <label class="text-sm font-medium text-neutral-700">
              {{ mode === 'login' ? copy.usernameOrEmail : copy.email }}
            </label>
            <n-input v-model:value="email" type="text" :placeholder="mode === 'login' ? copy.usernameOrEmailPlaceholder : 'name@example.com'" size="large">
              <template #prefix>
                <Mail :size="16" class="text-[#93a4b6]" />
              </template>
            </n-input>
          </div>

          <div class="space-y-1.5">
            <label class="text-sm font-medium text-neutral-700">{{ copy.password }}</label>
            <n-input v-model:value="password" type="password" show-password-on="click" :placeholder="copy.passwordPlaceholder" size="large">
              <template #prefix>
                <KeyRound :size="16" class="text-[#93a4b6]" />
              </template>
            </n-input>
          </div>

          <div v-if="mode === 'register'" class="space-y-1.5">
            <label class="text-sm font-medium text-neutral-700">{{ copy.confirmPassword }}</label>
            <n-input v-model:value="confirmPassword" type="password" show-password-on="click" :placeholder="copy.confirmPasswordPlaceholder" size="large">
              <template #prefix>
                <KeyRound :size="16" class="text-[#93a4b6]" />
              </template>
            </n-input>
          </div>

          <div class="py-1">
            <SliderCaptcha ref="captchaRef" @verify="onCaptchaVerify" />
          </div>

          <div class="grid gap-3 pt-2">
            <n-button type="primary" size="large" :loading="loading" @click="submit">
              <template #icon>
                <LogIn :size="18" />
              </template>
              {{ mode === 'login' ? copy.enterLogin : auth.isGuest ? copy.enterUpgrade : copy.enterRegister }}
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
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NCard, NInput, useMessage } from 'naive-ui'
import { BookOpenText, KeyRound, LogIn, Mail, SearchCheck, UserRound, WandSparkles } from '@lucide/vue'
import logoFull from '@/assets/logo-word.avif'
import SliderCaptcha from '@/components/SliderCaptcha.vue'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useLocaleStore } from '@/stores/locale'

const auth = useAuthStore()
const locale = useLocaleStore()
const router = useRouter()
const message = useMessage()
const mode = ref<'login' | 'register'>(auth.isGuest ? 'register' : 'login')
const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const captchaRef = ref<InstanceType<typeof SliderCaptcha>>()
const sliderToken = ref('')
const sliderX = ref(0)
const loading = ref(false)

function switchMode(m: 'login' | 'register') {
  mode.value = m
  sliderX.value = 0
  captchaRef.value?.reset()
}

onMounted(async () => {
  await fetchChallenge()
})

async function fetchChallenge() {
  try {
    const res = await api.post('/api/v1/auth/captcha/challenge')
    sliderToken.value = res.data.slider_token
  } catch {
    message.error(copy.value.captchaError)
  }
}

function onCaptchaVerify(x: number) {
  sliderX.value = x
}

const modeLabel = computed(() => {
  if (mode.value === 'login') return copy.value.login
  return auth.isGuest ? copy.value.upgradeAccount : copy.value.register
})
const modeHint = computed(() => {
  if (mode.value === 'login') return copy.value.loginHint
  return auth.isGuest ? copy.value.upgradeHint : copy.value.registerHint
})

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
        username: '用户名',
        usernamePlaceholder: '3-64位，字母、数字、下划线或连字符',
        usernameOrEmail: '用户名或邮箱',
        usernameOrEmailPlaceholder: '输入用户名或邮箱',
        email: '邮箱',
        password: '密码',
        passwordPlaceholder: '至少 8 位，包含字母和数字',
        confirmPassword: '确认密码',
        confirmPasswordPlaceholder: '请再次输入密码',
        passwordMismatch: '两次输入的密码不一致',
        enterLogin: '登录并进入工作台',
        enterRegister: '注册并进入工作台',
        upgradeAccount: '升级账号',
        upgradeHint: '设置用户名和密码，将当前游客身份升级为正式账号。',
        enterUpgrade: '升级并进入工作台',
        guestContinue: '以游客身份继续',
        captchaRequired: '请先完成滑块验证',
        captchaError: '验证加载失败，请刷新重试',
        loginSuccess: '登录成功',
        registerSuccess: '注册成功',
        networkError: '网络错误，请检查连接后重试',
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
        username: 'Username',
        usernamePlaceholder: '3-64 chars, letters, digits, _ or -',
        usernameOrEmail: 'Username or Email',
        usernameOrEmailPlaceholder: 'Enter username or email',
        email: 'Email',
        password: 'Password',
        passwordPlaceholder: 'At least 8 characters with letters and digits',
        confirmPassword: 'Confirm password',
        confirmPasswordPlaceholder: 'Re-enter your password',
        passwordMismatch: 'Passwords do not match',
        enterLogin: 'Login and enter workspace',
        enterRegister: 'Register and enter workspace',
        upgradeAccount: 'Upgrade account',
        upgradeHint: 'Set a username and password to upgrade your guest session to a full account.',
        enterUpgrade: 'Upgrade and enter workspace',
        guestContinue: 'Continue as guest',
        captchaRequired: 'Please complete the slider verification',
        captchaError: 'Failed to load captcha, please refresh',
        loginSuccess: 'Login successful',
        registerSuccess: 'Registration successful',
        networkError: 'Network error, please check your connection',
      }
)

function parse422(field: string, type: string): string {
  const zh = locale.isChinese
  // 按字段优先匹配
  if (field === 'username') {
    if (type.includes('missing')) return zh ? '请输入用户名' : 'Username is required'
    if (type.includes('pattern')) return zh ? '仅支持字母、数字、下划线、连字符' : 'Letters, digits, _ or - only'
    if (type.includes('short')) return zh ? '用户名至少3个字符' : 'Username too short (min 3)'
    if (type.includes('long')) return zh ? '用户名最多64个字符' : 'Username too long (max 64)'
  }
  if (field === 'email') {
    if (type.includes('missing')) return zh ? '请输入邮箱' : 'Email is required'
    if (type.includes('value_error')) return zh ? '邮箱格式不正确' : 'Invalid email format'
  }
  if (field === 'password') {
    if (type.includes('missing')) return zh ? '请输入密码' : 'Password is required'
    if (type.includes('type')) return zh ? '密码至少8位，包含字母和数字' : 'At least 8 chars with letters and digits'
  }
  if (field === 'slider_token') {
    if (type.includes('missing')) return zh ? '请完成滑块验证' : 'Please complete the slider'
  }
  if (field === 'slider_x') {
    if (type.includes('missing')) return zh ? '请完成滑块验证' : 'Please complete the slider'
  }
  // 通用兜底
  return type
}

function codeMessage(code: string): string {
  const zh = locale.isChinese
  const map: Record<string, string> = {
    AUTH_INVALID_CREDENTIALS: zh ? '用户名/邮箱或密码错误' : 'Incorrect username/email or password',
    AUTH_EMAIL_EXISTS: zh ? '该邮箱已被注册' : 'Email already registered',
    AUTH_USERNAME_EXISTS: zh ? '该用户名已被使用' : 'Username already taken',
    AUTH_WEAK_PASSWORD: zh ? '密码至少8位，需包含字母和数字' : 'Password must be at least 8 chars with letters and digits',
    AUTH_TOKEN_EXPIRED: zh ? '登录已过期，请重新登录' : 'Session expired, please login again',
    AUTH_TOKEN_BLACKLISTED: zh ? '令牌已失效' : 'Token has been revoked',
    AUTH_REFRESH_INVALID: zh ? '刷新令牌无效' : 'Invalid refresh token',
    AUTH_NOT_AUTHENTICATED: zh ? '请先登录' : 'Please login first',
    CAPTCHA_FAILED: zh ? '验证失败，请重试' : 'Verification failed, please retry',
    GUEST_FORBIDDEN: zh ? '请先登录后再操作' : 'Please login to continue',
    GUEST_NOT_FOUND: zh ? '游客身份未找到' : 'Guest identity not found',
    GUEST_ALREADY_REGISTERED: zh ? '当前已是注册用户' : 'Already a registered user',
  }
  return map[code] || code
}

async function submit() {
  // 从上往下逐字段校验，一次只报一个错误
  const zh = locale.isChinese
  if (mode.value !== 'login') {
    if (!username.value.trim()) {
      message.warning(zh ? '请输入用户名' : 'Username is required')
      return
    }
    if (!email.value.trim()) {
      message.warning(zh ? '请输入邮箱' : 'Email is required')
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)) {
      message.warning(zh ? '邮箱格式不正确' : 'Invalid email format')
      return
    }
    if (!password.value) {
      message.warning(zh ? '请输入密码' : 'Password is required')
      return
    }
    if (password.value.length < 8 || !/[A-Za-z]/.test(password.value) || !/\d/.test(password.value)) {
      message.warning(zh ? '密码至少8位，需包含字母和数字' : 'At least 8 chars with letters and digits')
      return
    }
    if (password.value !== confirmPassword.value) {
      message.warning(copy.value.passwordMismatch)
      return
    }
  } else {
    if (!email.value.trim()) {
      message.warning(zh ? '请输入用户名或邮箱' : 'Username or email is required')
      return
    }
    if (!password.value) {
      message.warning(zh ? '请输入密码' : 'Password is required')
      return
    }
  }
  if (!sliderX.value) {
    message.warning(copy.value.captchaRequired)
    return
  }

  loading.value = true

  try {
    // 提交前获取最新 captcha token，避免过期
    await fetchChallenge()

    if (mode.value === 'login') {
      await auth.login(email.value, password.value, sliderToken.value, sliderX.value)
    } else if (auth.isGuest) {
      await auth.upgrade(username.value, email.value, password.value, sliderToken.value, sliderX.value)
    } else {
      await auth.register(username.value, email.value, password.value, sliderToken.value, sliderX.value)
    }
    message.success(mode.value === 'login' ? copy.value.loginSuccess : copy.value.registerSuccess)
    router.push('/browse')
  } catch (e: any) {
    const status = e.response?.status
    const detail = e.response?.data?.detail

    // FastAPI 422 字段校验错误 — 只报第一条
    if (status === 422 && Array.isArray(detail)) {
      const err = detail[0]
      const field = err.loc?.[err.loc.length - 1] as string
      const label = field === 'username' ? copy.value.username
        : field === 'email' ? (mode.value === 'login' ? copy.value.usernameOrEmail : copy.value.email)
        : field === 'password' ? copy.value.password
        : field
      message.error(`[${label}] ${parse422(field, err.type)}`)
      return
    }

    // 业务错误码
    if (typeof detail === 'object' && detail?.code) {
      const code = detail.code
      if (code === 'CAPTCHA_FAILED') {
        captchaRef.value?.markFailed()
        message.error(codeMessage(code))
        await fetchChallenge()
        return
      }
      message.error(codeMessage(code))
      return
    }

    message.error(typeof detail === 'string' ? detail : copy.value.networkError)
  } finally {
    loading.value = false
  }
}

async function continueAsGuest() {
  await auth.guestLogin()
  router.push('/browse')
}
</script>
