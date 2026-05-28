import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api/client'

function persist(key: string, value: string | null) {
  if (value === null) {
    localStorage.removeItem(key)
  } else {
    localStorage.setItem(key, value)
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refreshToken'))
  const userId = ref<string | null>(localStorage.getItem('userId'))
  const isGuest = ref(localStorage.getItem('isGuest') === 'true')

  function setAuth(data: {
    access_token: string
    refresh_token: string
    user_id: string
    is_guest: boolean
  }) {
    token.value = data.access_token
    refreshToken.value = data.refresh_token
    userId.value = data.user_id
    isGuest.value = data.is_guest
    persist('token', data.access_token)
    persist('refreshToken', data.refresh_token)
    persist('userId', data.user_id)
    persist('isGuest', String(data.is_guest))
    api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`
  }

  async function guestLogin() {
    const FingerprintJS = await import('fingerprintjs')
    const fp = await FingerprintJS.load()
    const result = await fp.get()
    const res = await api.post('/api/v1/auth/guest', { fingerprint: result.visitorId })
    setAuth(res.data)
  }

  async function register(email: string, password: string) {
    const res = await api.post('/api/v1/auth/register', { email, password })
    setAuth(res.data)
  }

  async function login(email: string, password: string) {
    const form = new URLSearchParams()
    form.append('username', email)
    form.append('password', password)
    const res = await api.post('/api/v1/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    setAuth(res.data)
  }

  async function refreshAccessToken(): Promise<boolean> {
    if (!refreshToken.value) return false
    try {
      const res = await api.post('/api/v1/auth/refresh', {
        refresh_token: refreshToken.value,
      })
      setAuth(res.data)
      return true
    } catch {
      logout()
      return false
    }
  }

  async function logout() {
    try {
      await api.post('/api/v1/auth/logout')
    } catch {
      // 即使服务端请求失败也清除本地状态
    }
    token.value = null
    refreshToken.value = null
    userId.value = null
    isGuest.value = false
    localStorage.clear()
    delete api.defaults.headers.common['Authorization']
  }

  if (token.value) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
  }

  return { token, refreshToken, userId, isGuest, guestLogin, register, login, refreshAccessToken, logout }
})
