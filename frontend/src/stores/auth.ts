import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const userId = ref<string | null>(localStorage.getItem('userId'))
  const isGuest = ref(localStorage.getItem('isGuest') === 'true')

  function setAuth(data: { access_token: string; user_id: string; is_guest: boolean }) {
    token.value = data.access_token
    userId.value = data.user_id
    isGuest.value = data.is_guest
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('userId', data.user_id)
    localStorage.setItem('isGuest', String(data.is_guest))
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
    const res = await api.post('/api/v1/auth/login', null, {
      params: { username: email, password },
    })
    setAuth(res.data)
  }

  function logout() {
    token.value = null
    userId.value = null
    localStorage.clear()
    delete api.defaults.headers.common['Authorization']
  }

  if (token.value) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
  }

  return { token, userId, isGuest, guestLogin, register, login, logout }
})
