import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'

export interface User {
  id: number
  username: string
  role: 'admin' | 'editor' | 'operator'
  is_active: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const isAuthenticated = computed(() => user.value !== null)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isEditor = computed(() => user.value?.role === 'admin' || user.value?.role === 'editor')

  async function login(username: string, password: string): Promise<void> {
    const res = await api.post<{ user: User }>('/api/auth/login', { username, password })
    user.value = res.data.user
  }

  async function logout(): Promise<void> {
    await api.post('/api/auth/logout')
    user.value = null
  }

  async function fetchMe(): Promise<boolean> {
    try {
      const res = await api.get<User>('/api/auth/me')
      user.value = res.data
      return true
    } catch {
      user.value = null
      return false
    }
  }

  return { user, isAuthenticated, isAdmin, isEditor, login, logout, fetchMe }
})
