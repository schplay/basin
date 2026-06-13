<template>
  <AppLayout>
    <div class="p-6">
      <div class="flex items-center justify-between mb-6">
        <h1 class="text-2xl font-semibold">Dashboard</h1>
        <Button label="New Recording" icon="pi pi-circle-fill" severity="danger" @click="router.push('/recordings/new')" />
      </div>

      <!-- Active Recordings -->
      <section class="mb-8">
        <h2 class="text-sm font-semibold text-surface-400 uppercase tracking-wider mb-3">
          Active Recordings
          <span v-if="dashboard?.active_recording_count" class="ml-2 bg-red-500 text-white text-xs font-bold px-2 py-0.5 rounded-full">
            {{ dashboard.active_recording_count }}
          </span>
        </h2>

        <div v-if="isLoading" class="flex gap-4">
          <Skeleton v-for="i in 2" :key="i" width="300px" height="140px" class="rounded-xl" />
        </div>

        <div v-else-if="!dashboard?.active_recordings?.length"
          class="surface-card border border-surface-200 dark:border-surface-700 rounded-xl p-8 text-center text-surface-400">
          <i class="pi pi-circle text-3xl mb-3 block" />
          <p>No active recordings</p>
        </div>

        <div v-else class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          <div
            v-for="rec in dashboard.active_recordings"
            :key="rec.id"
            class="surface-card border border-red-500/40 rounded-xl p-5 cursor-pointer hover:border-red-500/70 transition-colors"
            @click="router.push(`/recordings/${rec.id}`)"
          >
            <div class="flex items-start justify-between mb-3">
              <div class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse inline-block" />
                <span class="text-xs text-surface-400 font-medium">{{ rec.group_name }}</span>
              </div>
              <Tag value="REC" severity="danger" class="text-xs" />
            </div>
            <p class="font-semibold text-lg leading-tight mb-1">{{ rec.name }}</p>
            <p class="text-sm text-surface-400 mb-3">{{ rec.channel_count }}ch · {{ (rec.sample_rate / 1000).toFixed(1) }}kHz / {{ rec.bit_depth }}b</p>
            <div class="font-mono text-2xl font-bold tracking-wider text-red-400">
              {{ liveDuration(rec.started_at) }}
            </div>
          </div>
        </div>
      </section>

      <!-- Storage + System row -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <!-- Storage -->
        <section>
          <h2 class="text-sm font-semibold text-surface-400 uppercase tracking-wider mb-3">Storage</h2>
          <div class="surface-card border border-surface-200 dark:border-surface-700 rounded-xl p-5">
            <div v-if="dashboard?.storage">
              <div class="flex items-center justify-between mb-2">
                <span class="font-medium">{{ dashboard.storage.name }}</span>
                <span class="text-sm text-surface-400">{{ formatBytes(dashboard.storage.used_bytes) }} / {{ formatBytes(dashboard.storage.total_bytes) }}</span>
              </div>
              <ProgressBar
                :value="dashboard.storage.used_percent"
                class="h-3"
                :pt="{
                  value: {
                    class: dashboard.storage.used_percent < 70
                      ? 'bg-green-500'
                      : dashboard.storage.used_percent < 90
                        ? 'bg-yellow-500'
                        : 'bg-red-500'
                  }
                }"
              />
              <p class="text-xs text-surface-400 mt-2">{{ dashboard.storage.used_percent.toFixed(1) }}% used</p>
            </div>
            <div v-else class="text-surface-400 text-sm">
              No active storage configured.
              <RouterLink to="/settings/storage" class="text-primary-400 hover:underline ml-1">Configure →</RouterLink>
            </div>
          </div>
        </section>

        <!-- System health -->
        <section>
          <h2 class="text-sm font-semibold text-surface-400 uppercase tracking-wider mb-3">System</h2>
          <div class="surface-card border border-surface-200 dark:border-surface-700 rounded-xl p-5">
            <div v-if="sysStatus" class="grid grid-cols-2 gap-3 text-sm">
              <div v-for="svc in serviceItems" :key="svc.label" class="flex items-center gap-2">
                <i :class="['text-base', svc.ok ? 'pi pi-check-circle text-green-400' : 'pi pi-times-circle text-red-400']" />
                <span>{{ svc.label }}</span>
              </div>
            </div>
            <div v-else class="text-surface-400 text-sm">Loading…</div>
          </div>
        </section>
      </div>

      <!-- Recent Recordings -->
      <section>
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-sm font-semibold text-surface-400 uppercase tracking-wider">Recent Recordings</h2>
          <RouterLink to="/recordings" class="text-sm text-primary-400 hover:underline">View all →</RouterLink>
        </div>

        <DataTable
          v-if="dashboard?.recent_recordings?.length"
          :value="dashboard.recent_recordings"
          class="surface-card border border-surface-200 dark:border-surface-700 rounded-xl"
          stripedRows
          size="small"
          selectionMode="single"
          @row-click="(e: any) => router.push(`/recordings/${e.data.id}`)"
        >
          <Column field="name" header="Name">
            <template #body="{ data }">
              <span class="font-medium cursor-pointer hover:text-primary-400 transition-colors">{{ data.name }}</span>
            </template>
          </Column>
          <Column field="group_name" header="Group" style="width: 160px" />
          <Column header="Status" style="width: 110px">
            <template #body="{ data }">
              <Tag :value="data.status" :severity="statusSeverity(data.status)" class="text-xs capitalize" />
            </template>
          </Column>
          <Column field="channel_count" header="Ch" style="width: 60px" />
          <Column header="Duration" style="width: 110px">
            <template #body="{ data }">
              {{ data.duration_seconds ? formatDuration(data.duration_seconds) : '—' }}
            </template>
          </Column>
          <Column header="Created" style="width: 160px">
            <template #body="{ data }">{{ formatDate(data.created_at) }}</template>
          </Column>
        </DataTable>

        <div v-else-if="!isLoading" class="text-surface-400 text-sm text-center py-8">
          No recordings yet.
        </div>
      </section>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { api } from '@/api/client'
import AppLayout from '@/components/AppLayout.vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import ProgressBar from 'primevue/progressbar'
import Skeleton from 'primevue/skeleton'

const router = useRouter()

const { data: dashboard, isLoading } = useQuery({
  queryKey: ['dashboard'],
  queryFn: async () => (await api.get('/api/dashboard')).data,
  refetchInterval: 10_000,
})

const { data: sysStatus } = useQuery({
  queryKey: ['status'],
  queryFn: async () => (await api.get('/api/status')).data,
  refetchInterval: 30_000,
})

const serviceItems = computed(() => {
  if (!sysStatus.value) return []
  const s = sysStatus.value.services ?? {}
  const active = (key: string) => s[key] === 'active'
  return [
    { label: 'API', ok: active('basin-api') },
    { label: 'AES67 Daemon', ok: active('basin-aes67') },
    { label: 'Worker', ok: active('basin-worker') },
    { label: 'PostgreSQL', ok: active('postgresql') },
  ]
})

// Live duration timer updates every 500 ms
const now = ref(Date.now())
let timer: ReturnType<typeof setInterval>
onMounted(() => { timer = setInterval(() => { now.value = Date.now() }, 500) })
onUnmounted(() => clearInterval(timer))

function liveDuration(startedAt: string | null): string {
  if (!startedAt) return '0:00:00'
  const elapsed = (now.value - new Date(startedAt).getTime()) / 1000
  return formatDuration(elapsed)
}

function formatDuration(s: number): string {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

function formatBytes(bytes: number): string {
  if (bytes >= 1e12) return (bytes / 1e12).toFixed(1) + ' TB'
  if (bytes >= 1e9) return (bytes / 1e9).toFixed(1) + ' GB'
  if (bytes >= 1e6) return (bytes / 1e6).toFixed(0) + ' MB'
  return bytes + ' B'
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function statusSeverity(s: string) {
  switch (s) {
    case 'completed': return 'success'
    case 'error': return 'warn'
    case 'playback': return 'info'
    default: return 'secondary'
  }
}
</script>
