import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/setup', name: 'setup', component: () => import('@/views/SetupView.vue'), meta: { public: true } },
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    { path: '/status', name: 'status', component: () => import('@/views/StatusView.vue'), meta: { public: true } },
    { path: '/', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
    { path: '/sources', name: 'sources', component: () => import('@/views/SourcesView.vue') },
    { path: '/recordings', name: 'recordings', component: () => import('@/views/RecordingsView.vue') },
    { path: '/recordings/new', name: 'new-recording', component: () => import('@/views/NewRecordingView.vue') },
    { path: '/recordings/:id', name: 'recording-detail', component: () => import('@/views/RecordingDetailView.vue') },
    { path: '/groups', name: 'groups', component: () => import('@/views/GroupsView.vue') },
    { path: '/templates', name: 'templates', component: () => import('@/views/TemplatesView.vue') },
    { path: '/consoles', name: 'consoles', component: () => import('@/views/ConsolesView.vue') },
    { path: '/settings/storage', name: 'storage', component: () => import('@/views/StorageView.vue') },
    { path: '/settings/network', name: 'network', component: () => import('@/views/NetworkView.vue') },
    { path: '/settings/users', name: 'users', component: () => import('@/views/UsersView.vue') },
    { path: '/audit', name: 'audit', component: () => import('@/views/AuditView.vue') },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true

  const auth = useAuthStore()

  if (!auth.isAuthenticated) {
    const ok = await auth.fetchMe()
    if (!ok) {
      // Check if setup is needed first
      try {
        const res = await api.get<{ complete: boolean }>('/api/setup/status')
        if (!res.data.complete) return { name: 'setup' }
      } catch { /* ignore */ }
      return { name: 'login' }
    }
  }

  return true
})

export default router
