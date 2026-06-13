import axios from 'axios'

export const api = axios.create({
  baseURL: '/',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

let isRefreshing = false
let refreshQueue: Array<(ok: boolean) => void> = []

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error)
    }
    if (original.url?.includes('/api/auth/')) {
      return Promise.reject(error)
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        refreshQueue.push((ok) => {
          if (ok) resolve(api(original))
          else reject(error)
        })
      })
    }

    original._retry = true
    isRefreshing = true

    try {
      await api.post('/api/auth/refresh')
      refreshQueue.forEach((cb) => cb(true))
      return api(original)
    } catch {
      refreshQueue.forEach((cb) => cb(false))
      window.location.href = '/login'
      return Promise.reject(error)
    } finally {
      isRefreshing = false
      refreshQueue = []
    }
  },
)
