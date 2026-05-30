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
  const username = ref<string | null>(localStorage.getItem('username'))
  const avatarUrl = ref<string | null>(localStorage.getItem('avatarUrl'))
  const isGuest = ref(localStorage.getItem('isGuest') === 'true')

  function setAuth(data: {
    access_token: string
    refresh_token: string
    user_id: string
    username: string | null
    avatar_url: string | null
    is_guest: boolean
  }) {
    token.value = data.access_token
    refreshToken.value = data.refresh_token
    userId.value = data.user_id
    username.value = data.username
    avatarUrl.value = data.avatar_url
    isGuest.value = data.is_guest
    persist('token', data.access_token)
    persist('refreshToken', data.refresh_token)
    persist('userId', data.user_id)
    persist('username', data.username)
    persist('avatarUrl', data.avatar_url)
    persist('isGuest', String(data.is_guest))
    api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`
  }

  function setGuest(data: { user_id: string; is_guest: boolean }) {
    token.value = null
    refreshToken.value = null
    userId.value = data.user_id
    username.value = null
    avatarUrl.value = null
    isGuest.value = data.is_guest
    persist('token', null)
    persist('refreshToken', null)
    persist('userId', data.user_id)
    persist('username', null)
    persist('avatarUrl', null)
    persist('isGuest', String(data.is_guest))
    delete api.defaults.headers.common['Authorization']
  }

  async function guestLogin() {
    const res = await api.post('/api/v1/auth/guest')
    setGuest(res.data)
  }

  async function register(username: string, email: string, password: string, sliderToken: string, sliderX: number) {
    const res = await api.post('/api/v1/auth/register', { username, email, password, slider_token: sliderToken, slider_x: sliderX })
    setAuth(res.data)
  }

  async function login(usernameOrEmail: string, password: string, sliderToken: string, sliderX: number) {
    const form = new URLSearchParams()
    form.append('username', usernameOrEmail)
    form.append('password', password)
    form.append('slider_token', sliderToken)
    form.append('slider_x', String(sliderX))
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

  async function upgrade(username: string, email: string, password: string, sliderToken: string, sliderX: number) {
    const res = await api.post('/api/v1/auth/upgrade', { username, email, password, slider_token: sliderToken, slider_x: sliderX })
    setAuth(res.data)
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
    username.value = null
    avatarUrl.value = null
    isGuest.value = false
    localStorage.clear()
    delete api.defaults.headers.common['Authorization']
  }

  if (token.value) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
  }

  return { token, refreshToken, userId, username, avatarUrl, isGuest, guestLogin, register, login, upgrade, refreshAccessToken, logout }
})
