import axios from 'axios'
import type { AxiosError, InternalAxiosRequestConfig } from 'axios'

const api = axios.create({
  baseURL: '/',
  timeout: 30000,
  withCredentials: true,
})

let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (err: unknown) => void
}> = []

function processQueue(error: unknown, token: string | null) {
  failedQueue.forEach((p) => {
    if (error) {
      p.reject(error)
    } else {
      p.resolve(token!)
    }
  })
  failedQueue = []
}

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // 403 游客无权操作 → 跳转登录页
    if (error.response?.status === 403) {
      const code = (error.response?.data as any)?.detail?.code
      if (code === 'GUEST_FORBIDDEN') {
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }

    // 401 token 过期 → 尝试自动刷新
    if (error.response?.status === 401 && !originalRequest._retry) {
      const code = (error.response?.data as any)?.detail?.code

      if (code === 'AUTH_TOKEN_EXPIRED' || code === 'AUTH_NOT_AUTHENTICATED') {
        if (isRefreshing) {
          // 正在刷新中，排队等待
          return new Promise<string>((resolve, reject) => {
            failedQueue.push({ resolve, reject })
          }).then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            return api(originalRequest)
          })
        }

        originalRequest._retry = true
        isRefreshing = true

        try {
          const refreshToken = localStorage.getItem('refreshToken')
          if (!refreshToken) throw new Error('no refresh token')

          const res = await axios.post('/api/v1/auth/refresh', {
            refresh_token: refreshToken,
          })

          const data = res.data
          localStorage.setItem('token', data.access_token)
          localStorage.setItem('refreshToken', data.refresh_token)
          localStorage.setItem('userId', data.user_id)
          localStorage.setItem('username', data.username)
          localStorage.setItem('avatarUrl', data.avatar_url)
          localStorage.setItem('isGuest', String(data.is_guest))

          api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`
          processQueue(null, data.access_token)

          originalRequest.headers.Authorization = `Bearer ${data.access_token}`
          return api(originalRequest)
        } catch (refreshError) {
          processQueue(refreshError, null)
          localStorage.clear()
          delete api.defaults.headers.common['Authorization']
          window.location.href = '/login'
          return Promise.reject(refreshError)
        } finally {
          isRefreshing = false
        }
      }
    }

    return Promise.reject(error)
  },
)

export default api
