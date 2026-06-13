<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import Button from 'primevue/button'

const auth = useAuthStore()
const router = useRouter()

const navItems = [
  { label: 'Dashboard', icon: 'pi-home', to: '/' },
  { label: 'Sources', icon: 'pi-wifi', to: '/sources' },
  { label: 'Groups', icon: 'pi-folder', to: '/groups' },
  { label: 'Templates', icon: 'pi-copy', to: '/templates' },
  { label: 'Recordings', icon: 'pi-circle-fill', to: '/recordings' },
  { label: 'Consoles', icon: 'pi-sliders-h', to: '/consoles' },
]

const adminItems = [
  { label: 'Storage', icon: 'pi-database', to: '/settings/storage' },
  { label: 'Network', icon: 'pi-server', to: '/settings/network' },
  { label: 'Users', icon: 'pi-users', to: '/settings/users' },
  { label: 'Audit Log', icon: 'pi-list', to: '/audit' },
  { label: 'System', icon: 'pi-cog', to: '/settings/system' },
]

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="flex h-screen bg-gray-50 dark:bg-gray-950">
    <!-- Sidebar -->
    <aside class="w-56 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
      <div class="p-5 border-b border-gray-800">
        <h1 class="text-xl font-bold text-white tracking-tight">Basin</h1>
        <p class="text-gray-500 text-xs mt-0.5">{{ auth.user?.username }}</p>
      </div>

      <nav class="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
          active-class="bg-gray-800 text-white"
        >
          <i :class="`pi ${item.icon} text-base`"></i>
          {{ item.label }}
        </RouterLink>

        <div v-if="auth.isAdmin" class="pt-4 pb-1 px-3">
          <p class="text-xs font-semibold text-gray-600 uppercase tracking-wider">Settings</p>
        </div>

        <RouterLink
          v-if="auth.isAdmin"
          v-for="item in adminItems"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
          active-class="bg-gray-800 text-white"
        >
          <i :class="`pi ${item.icon} text-base`"></i>
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="p-3 border-t border-gray-800">
        <button
          class="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
          @click="logout"
        >
          <i class="pi pi-sign-out text-base"></i>
          Sign out
        </button>
      </div>
    </aside>

    <!-- Main content -->
    <main class="flex-1 overflow-y-auto">
      <slot />
    </main>
  </div>
</template>
