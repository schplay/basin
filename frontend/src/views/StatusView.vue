<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { api } from '@/api/client'

interface ServiceHealth {
  [key: string]: string
}

interface StorageInfo {
  path: string
  total_gb: number
  used_gb: number
  free_gb: number
}

interface Interface {
  name: string
  ip: string | null
  mac: string | null
}

interface StatusData {
  hostname: string
  version: string
  interfaces: Interface[]
  services: ServiceHealth
  active_recordings: number
  storage: StorageInfo | null
}

const data = ref<StatusData | null>(null)
const lastUpdated = ref<Date | null>(null)
let timer: ReturnType<typeof setInterval> | null = null

async function fetch() {
  try {
    const res = await api.get<StatusData>('/api/status')
    data.value = res.data
    lastUpdated.value = new Date()
  } catch { /* keep showing stale data */ }
}

function serviceColor(status: string) {
  if (status === 'active') return 'bg-green-500'
  if (status === 'inactive') return 'bg-gray-500'
  return 'bg-red-500'
}

function storagePercent(s: StorageInfo) {
  return Math.round((s.used_gb / s.total_gb) * 100)
}

onMounted(() => {
  fetch()
  timer = setInterval(fetch, 10_000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="min-h-screen bg-gray-950 text-white p-8 flex flex-col gap-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-4xl font-bold tracking-tight text-white">Basin</h1>
        <p v-if="data" class="text-gray-400 text-lg mt-0.5">{{ data.hostname }}</p>
      </div>
      <div class="text-right text-gray-500 text-sm">
        <p>v{{ data?.version }}</p>
        <p v-if="lastUpdated">Updated {{ lastUpdated.toLocaleTimeString() }}</p>
      </div>
    </div>

    <!-- Active recordings badge -->
    <div v-if="data" class="flex items-center gap-3">
      <div
        class="px-4 py-2 rounded-xl text-lg font-semibold"
        :class="data.active_recordings > 0 ? 'bg-red-600/30 text-red-300 border border-red-600' : 'bg-gray-800 text-gray-400'"
      >
        <span class="inline-block w-2.5 h-2.5 rounded-full mr-2" :class="data.active_recordings > 0 ? 'bg-red-500 animate-pulse' : 'bg-gray-600'"></span>
        {{ data.active_recordings > 0 ? `${data.active_recordings} recording${data.active_recordings > 1 ? 's' : ''} active` : 'No active recordings' }}
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 flex-1">
      <!-- Network interfaces -->
      <div class="bg-gray-900 rounded-2xl p-6 border border-gray-800">
        <h2 class="text-gray-400 text-sm font-semibold uppercase tracking-wider mb-4">Network</h2>
        <div v-if="data" class="space-y-3">
          <div
            v-for="iface in data.interfaces.filter(i => i.ip)"
            :key="iface.name"
            class="flex items-center justify-between"
          >
            <span class="text-gray-300 font-mono text-sm">{{ iface.name }}</span>
            <span class="text-white font-mono text-lg font-semibold">{{ iface.ip }}</span>
          </div>
          <p v-if="!data.interfaces.some(i => i.ip)" class="text-gray-500 text-sm">No IP addresses assigned</p>
        </div>
        <div v-else class="animate-pulse space-y-3">
          <div class="h-6 bg-gray-800 rounded w-3/4"></div>
          <div class="h-6 bg-gray-800 rounded w-1/2"></div>
        </div>
      </div>

      <!-- Service health -->
      <div class="bg-gray-900 rounded-2xl p-6 border border-gray-800">
        <h2 class="text-gray-400 text-sm font-semibold uppercase tracking-wider mb-4">Services</h2>
        <div v-if="data" class="space-y-2.5">
          <div v-for="(status, name) in data.services" :key="name" class="flex items-center justify-between">
            <span class="text-gray-300 font-mono text-sm">{{ name }}</span>
            <div class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full" :class="serviceColor(status)"></span>
              <span class="text-sm" :class="status === 'active' ? 'text-green-400' : status === 'unknown' ? 'text-gray-500' : 'text-red-400'">
                {{ status }}
              </span>
            </div>
          </div>
        </div>
        <div v-else class="animate-pulse space-y-3">
          <div v-for="i in 5" :key="i" class="h-5 bg-gray-800 rounded"></div>
        </div>
      </div>

      <!-- Storage -->
      <div v-if="data?.storage" class="bg-gray-900 rounded-2xl p-6 border border-gray-800 md:col-span-2">
        <h2 class="text-gray-400 text-sm font-semibold uppercase tracking-wider mb-4">Storage</h2>
        <p class="text-gray-500 font-mono text-sm mb-3">{{ data.storage.path }}</p>
        <div class="w-full bg-gray-800 rounded-full h-3 mb-2">
          <div
            class="h-3 rounded-full transition-all"
            :class="storagePercent(data.storage) > 90 ? 'bg-red-500' : storagePercent(data.storage) > 75 ? 'bg-yellow-500' : 'bg-green-500'"
            :style="{ width: `${storagePercent(data.storage)}%` }"
          ></div>
        </div>
        <div class="flex justify-between text-sm text-gray-400">
          <span>{{ data.storage.used_gb }} GB used</span>
          <span>{{ data.storage.free_gb }} GB free of {{ data.storage.total_gb }} GB</span>
        </div>
      </div>
    </div>
  </div>
</template>
