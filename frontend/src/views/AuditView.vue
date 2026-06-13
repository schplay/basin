<template>
  <AppLayout>
    <div class="p-6 max-w-6xl">
      <h1 class="text-2xl font-semibold mb-6">Audit Log</h1>

      <!-- Filters -->
      <div class="flex flex-wrap gap-3 mb-5">
        <InputText v-model="filterAction" placeholder="Filter action…" class="w-44" size="small"
          @update:modelValue="debouncedLoad" />
        <Select v-model="filterResourceType" :options="resourceTypeOptions" option-label="label"
          option-value="value" placeholder="Resource type" class="w-44" size="small"
          showClear @change="load" />
        <Select v-model="filterUserId" :options="userOptions" option-label="label"
          option-value="value" placeholder="User" class="w-44" size="small"
          showClear @change="load" />
        <Button icon="pi pi-refresh" severity="secondary" size="small" @click="load" />
      </div>

      <DataTable
        :value="items"
        :loading="loading"
        stripedRows
        size="small"
        class="surface-card border border-surface-200 dark:border-surface-700 rounded-xl"
      >
        <Column header="Time" style="width: 170px">
          <template #body="{ data }">{{ formatDate(data.created_at) }}</template>
        </Column>
        <Column field="username" header="User" style="width: 130px">
          <template #body="{ data }">
            <span class="font-mono text-xs">{{ data.username ?? '—' }}</span>
          </template>
        </Column>
        <Column field="action" header="Action" style="width: 180px">
          <template #body="{ data }">
            <Tag :value="data.action" :severity="actionSeverity(data.action)" class="text-xs font-mono" />
          </template>
        </Column>
        <Column header="Resource" style="width: 160px">
          <template #body="{ data }">
            <span v-if="data.resource_type" class="text-xs text-surface-400">
              {{ data.resource_type }}
              <span v-if="data.resource_id" class="font-mono">#{{ data.resource_id }}</span>
            </span>
            <span v-else class="text-surface-600">—</span>
          </template>
        </Column>
        <Column header="Detail">
          <template #body="{ data }">
            <span class="font-mono text-xs text-surface-400">
              {{ detailSummary(data.detail) }}
            </span>
          </template>
        </Column>
      </DataTable>

      <!-- Pagination -->
      <div class="flex items-center justify-between mt-4">
        <p class="text-sm text-surface-400">
          Showing {{ offset + 1 }}–{{ Math.min(offset + limit, total) }} of {{ total }}
        </p>
        <div class="flex gap-2">
          <Button label="Previous" icon="pi pi-chevron-left" size="small" severity="secondary"
            :disabled="offset === 0" @click="offset = Math.max(0, offset - limit); load()" />
          <Button label="Next" icon="pi pi-chevron-right" iconPos="right" size="small" severity="secondary"
            :disabled="offset + limit >= total" @click="offset += limit; load()" />
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { api } from '@/api/client'
import AppLayout from '@/components/AppLayout.vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'

interface AuditEntry {
  id: number
  user_id: number | null
  username: string | null
  action: string
  resource_type: string | null
  resource_id: number | null
  detail: Record<string, any>
  created_at: string
}

const items = ref<AuditEntry[]>([])
const total = ref(0)
const loading = ref(false)
const offset = ref(0)
const limit = 50

const filterAction = ref('')
const filterResourceType = ref<string | null>(null)
const filterUserId = ref<number | null>(null)

const resourceTypeOptions = [
  { label: 'Recording', value: 'recording' },
  { label: 'Group', value: 'group' },
  { label: 'User', value: 'user' },
  { label: 'Storage', value: 'storage' },
]

const { data: users } = useQuery({
  queryKey: ['users'],
  queryFn: () => api.get('/api/users').then(r => r.data),
})

const userOptions = computed(() => {
  const opts = (users.value ?? []) as any[]
  return opts.map(u => ({ label: u.username, value: u.id }))
})

async function load() {
  loading.value = true
  try {
    const params: Record<string, any> = { limit, offset: offset.value }
    if (filterAction.value) params.action = filterAction.value
    if (filterResourceType.value) params.resource_type = filterResourceType.value
    if (filterUserId.value) params.user_id = filterUserId.value
    const resp = await api.get('/api/audit', { params })
    items.value = resp.data.items
    total.value = resp.data.total
  } finally {
    loading.value = false
  }
}

let debounceTimer: ReturnType<typeof setTimeout>
function debouncedLoad() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => { offset.value = 0; load() }, 350)
}

onMounted(load)

function formatDate(iso: string) {
  return new Date(iso).toLocaleString()
}

function detailSummary(detail: Record<string, any>): string {
  return Object.entries(detail)
    .slice(0, 3)
    .map(([k, v]) => `${k}=${v}`)
    .join('  ')
}

function actionSeverity(action: string): 'danger' | 'warn' | 'info' | 'success' | 'secondary' {
  if (action.includes('delete') || action.includes('stop') || action.includes('deactivate')) return 'danger'
  if (action.includes('start') || action.includes('create')) return 'success'
  if (action.includes('update') || action.includes('export')) return 'info'
  return 'secondary'
}
</script>
