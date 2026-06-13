<template>
  <AppLayout>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-semibold">Recordings</h1>
      <Button label="New Recording" icon="pi pi-plus" @click="router.push('/recordings/new')" />
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-3 mb-4">
      <Select
        v-model="filterGroupId"
        :options="flatGroups"
        optionLabel="label"
        optionValue="value"
        placeholder="All groups"
        showClear
        class="w-56"
      />
      <Select
        v-model="filterStatus"
        :options="STATUS_OPTIONS"
        optionLabel="label"
        optionValue="value"
        placeholder="Any status"
        showClear
        class="w-44"
      />
    </div>

    <div v-if="isLoading" class="flex justify-center py-12">
      <ProgressSpinner />
    </div>

    <div v-else-if="!recordings?.length" class="text-center py-16 text-surface-400">
      <i class="pi pi-microphone text-5xl mb-4 block" />
      <p class="text-lg mb-2">No recordings yet</p>
      <p class="text-sm mb-6">Create a new recording to get started</p>
      <Button label="New Recording" icon="pi pi-plus" @click="router.push('/recordings/new')" />
    </div>

    <DataTable
      v-else
      :value="recordings"
      class="surface-card rounded-xl border border-surface-200 dark:border-surface-700"
      stripedRows
      selectionMode="single"
      @row-click="(e) => router.push(`/recordings/${e.data.id}`)"
    >
      <Column field="name" header="Name" sortable>
        <template #body="{ data }">
          <span class="font-medium cursor-pointer hover:text-primary-400 transition-colors">{{ data.name }}</span>
        </template>
      </Column>
      <Column header="Status" style="width: 130px">
        <template #body="{ data }">
          <Tag :value="data.status" :severity="statusSeverity(data.status)" />
        </template>
      </Column>
      <Column field="channel_count" header="Channels" style="width: 100px" />
      <Column header="Duration" style="width: 110px">
        <template #body="{ data }">
          <span v-if="data.duration_seconds">{{ formatDuration(data.duration_seconds) }}</span>
          <span v-else class="text-surface-400">—</span>
        </template>
      </Column>
      <Column field="sample_rate" header="Format" style="width: 140px">
        <template #body="{ data }">{{ data.sample_rate / 1000 }}kHz / {{ data.bit_depth }}b</template>
      </Column>
      <Column field="created_at" header="Created" sortable style="width: 160px">
        <template #body="{ data }">{{ formatDate(data.created_at) }}</template>
      </Column>
    </DataTable>
  </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { api } from '@/api/client'
import AppLayout from '@/components/AppLayout.vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Select from 'primevue/select'
import ProgressSpinner from 'primevue/progressspinner'

const router = useRouter()

const filterGroupId = ref<number | null>(null)
const filterStatus = ref<string | null>(null)

const STATUS_OPTIONS = [
  { label: 'Pending', value: 'pending' },
  { label: 'Recording', value: 'recording' },
  { label: 'Completed', value: 'completed' },
  { label: 'Error', value: 'error' },
]

const { data: groups } = useQuery({
  queryKey: ['groups'],
  queryFn: async () => (await api.get('/api/groups')).data,
})

const flatGroups = computed(() => {
  const result: { label: string; value: number }[] = []
  function walk(list: any[], prefix = '') {
    for (const g of list ?? []) {
      result.push({ label: prefix + g.name, value: g.id })
      walk(g.children ?? [], prefix + '  ')
    }
  }
  walk(groups.value ?? [])
  return result
})

const queryParams = computed(() => {
  const p: Record<string, any> = {}
  if (filterGroupId.value) p.group_id = filterGroupId.value
  if (filterStatus.value) p.status = filterStatus.value
  return p
})

const { data: recordings, isLoading } = useQuery({
  queryKey: ['recordings', queryParams],
  queryFn: async () => (await api.get('/api/recordings', { params: queryParams.value })).data,
})

function statusSeverity(status: string) {
  switch (status) {
    case 'recording': return 'danger'
    case 'completed': return 'success'
    case 'error': return 'warn'
    default: return 'secondary'
  }
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>
