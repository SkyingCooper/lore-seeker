<template>
  <div class="login-page">
    <div class="card">
      <h2>{{ mode === 'login' ? '登录' : '注册' }}</h2>
      <input v-model="email" type="email" placeholder="邮箱" />
      <input v-model="password" type="password" placeholder="密码" />
      <button @click="submit" :disabled="loading">
        {{ loading ? '处理中...' : (mode === 'login' ? '登录' : '注册') }}
      </button>
      <p class="toggle">
        {{ mode === 'login' ? '没有账号？' : '已有账号？' }}
        <a @click="mode = mode === 'login' ? 'register' : 'login'">
          {{ mode === 'login' ? '注册' : '登录' }}
        </a>
      </p>
      <p class="guest-link">
        <a @click="continueAsGuest">以游客身份继续</a>
      </p>
      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const mode = ref<'login' | 'register'>('login')
const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

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

<style scoped>
.login-page { display: flex; align-items: center; justify-content: center; height: 100vh; background: #f0f2f5; }
.card { background: #fff; padding: 40px; border-radius: 12px; width: 360px; display: flex; flex-direction: column; gap: 14px; box-shadow: 0 4px 24px rgba(0,0,0,.08); }
h2 { margin: 0; font-size: 22px; }
input { padding: 10px 14px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; }
button { padding: 10px; background: #7c83fd; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 15px; }
button:disabled { opacity: .6; }
.toggle, .guest-link { font-size: 13px; text-align: center; }
.toggle a, .guest-link a { color: #7c83fd; cursor: pointer; }
.error { color: #e53e3e; font-size: 13px; }
</style>
