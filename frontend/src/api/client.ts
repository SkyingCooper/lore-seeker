import axios from 'axios'

const api = axios.create({
  baseURL: '/',
  timeout: 30000,
  withCredentials: true,
})

api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 403) {
      const code = error.response?.data?.detail?.code
      if (code === 'GUEST_FORBIDDEN') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

export default api
