<template>
  <AppLayout>
    <ConfirmDialog />
    <Toast />
    <div class="p-6 max-w-5xl">
      <div class="flex items-center justify-between mb-6">
        <div>
          <h1 class="text-2xl font-semibold">Consoles</h1>
          <p class="text-sm text-surface-400 mt-0.5">Behringer X32 / Wing OSC integrations</p>
        </div>
        <Button label="Add Console" icon="pi pi-plus" @click="openCreate" />
      </div>

      <DataTable
        :value="consoles ?? []"
        :loading="isPending"
        stripedRows
        class="text-sm"
      >
        <Column field="name" header="Name" />
        <Column header="Type" style="width: 130px">
          <template #body="{ data }">
            <Tag :value="consoleLabel(data.console_type)" severity="secondary" class="text-xs" />
          </template>
        </Column>
        <Column field="ip_address" header="IP Address" style="width: 160px" />
        <Column field="port" header="Port" style="width: 80px" />
        <Column header="Last Seen" style="width: 180px">
          <template #body="{ data }">
            {{ data.last_connected_at ? formatDate(data.last_connected_at) : '—' }}
          </template>
        </Column>
        <Column header="Active" style="width: 80px">
          <template #body="{ data }">
            <i :class="data.is_active ? 'pi pi-check-circle text-green-400' : 'pi pi-ban text-surface-500'" />
          </template>
        </Column>
        <Column header="Actions" style="width: 160px">
          <template #body="{ data }">
            <div class="flex gap-1">
              <Button
                icon="pi pi-wifi"
                text rounded size="small"
                severity="info"
                title="Ping"
                :loading="pinging[data.id]"
                @click="doPing(data)"
              />
              <Button
                icon="pi pi-list"
                text rounded size="small"
                severity="secondary"
                title="Fetch channel names"
                @click="openChannelNames(data)"
              />
              <Button icon="pi pi-pencil" text rounded size="small" @click="openEdit(data)" />
              <Button icon="pi pi-trash" text rounded size="small" severity="danger" @click="confirmDelete(data)" />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>

    <!-- Create / Edit dialog -->
    <Dialog
      v-model:visible="dialogVisible"
      :header="editingId ? 'Edit Console' : 'Add Console'"
      modal
      style="width: 30rem"
    >
      <div class="space-y-4 py-2">
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium">Name</label>
          <InputText v-model="form.name" placeholder="FOH X32" class="w-full" />
        </div>
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium">Console Type</label>
          <Select
            v-model="form.console_type"
            :options="consoleTypeOptions"
            option-label="label"
            option-value="value"
            class="w-full"
            @change="onTypeChange"
          />
        </div>
        <div class="grid grid-cols-3 gap-3">
          <div class="col-span-2 flex flex-col gap-1.5">
            <label class="text-sm font-medium">IP Address</label>
            <InputText v-model="form.ip_address" placeholder="192.168.1.100" class="w-full" />
          </div>
          <div class="flex flex-col gap-1.5">
            <label class="text-sm font-medium">UDP Port</label>
            <InputNumber v-model="form.port" :min="1" :max="65535" class="w-full" />
          </div>
        </div>
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium">Network Interface <span class="text-surface-500 font-normal">(optional)</span></label>
          <InputText v-model="form.network_interface" placeholder="eth0" class="w-full" />
        </div>
        <div class="flex items-center gap-2">
          <Checkbox v-model="form.is_active" :binary="true" inputId="is_active" />
          <label for="is_active" class="text-sm">Active</label>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="dialogVisible = false" />
        <Button label="Save" :loading="saveMutation.isPending.value" @click="saveMutation.mutate()" />
      </template>
    </Dialog>

    <!-- Channel Names dialog -->
    <Dialog
      v-model:visible="channelNamesVisible"
      :header="`Channel Names — ${channelNamesSource?.name ?? ''}`"
      modal
      style="width: 26rem"
    >
      <div class="py-2">
        <div class="flex items-center gap-3 mb-4">
          <InputNumber v-model="fetchCount" :min="1" :max="40" class="w-24" size="small" />
          <label class="text-sm text-surface-400">channels to fetch</label>
          <Button
            label="Fetch"
            icon="pi pi-download"
            size="small"
            :loading="fetchingNames"
            @click="fetchNames"
          />
        </div>

        <div v-if="channelNames.length" class="max-h-64 overflow-y-auto">
          <div
            v-for="(name, idx) in channelNames"
            :key="idx"
            class="flex items-center gap-3 py-1.5 border-b border-surface-800 text-sm"
          >
            <span class="font-mono text-surface-500 w-8 text-right shrink-0">{{ idx + 1 }}</span>
            <span class="flex-1">{{ name || '—' }}</span>
          </div>
        </div>
        <p v-else-if="!fetchingNames" class="text-surface-500 text-sm text-center py-4">
          Click Fetch to read names from the console.
        </p>
        <div v-else class="flex justify-center py-4">
          <ProgressSpinner style="width: 32px; height: 32px" />
        </div>
      </div>
      <template #footer>
        <Button label="Close" severity="secondary" @click="channelNamesVisible = false" />
        <Button
          v-if="channelNames.length"
          label="Copy to Clipboard"
          icon="pi pi-copy"
          severity="secondary"
          @click="copyNames"
        />
      </template>
    </Dialog>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { api } from '@/api/client'
import AppLayout from '@/components/AppLayout.vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Checkbox from 'primevue/checkbox'
import ConfirmDialog from 'primevue/confirmdialog'
import ProgressSpinner from 'primevue/progressspinner'
import Toast from 'primevue/toast'

interface Console {
  id: number
  name: string
  console_type: 'behringer_x32' | 'behringer_wing'
  ip_address: string
  port: number
  network_interface: string | null
  is_active: boolean
  last_connected_at: string | null
}

const qc = useQueryClient()
const toast = useToast()
const confirm = useConfirm()

const { data: consoles, isPending } = useQuery<Console[]>({
  queryKey: ['consoles'],
  queryFn: () => api.get('/api/consoles').then(r => r.data),
})

const consoleTypeOptions = [
  { label: 'Behringer X32', value: 'behringer_x32' },
  { label: 'Behringer Wing', value: 'behringer_wing' },
]

const DEFAULT_PORT: Record<string, number> = {
  behringer_x32: 10023,
  behringer_wing: 2223,
}

function consoleLabel(type: string) {
  return type === 'behringer_x32' ? 'X32' : 'Wing'
}

// ── Create / Edit ─────────────────────────────────────────────
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const form = ref({ name: '', console_type: 'behringer_x32', ip_address: '', port: 10023, network_interface: '', is_active: true })

function openCreate() {
  editingId.value = null
  form.value = { name: '', console_type: 'behringer_x32', ip_address: '', port: 10023, network_interface: '', is_active: true }
  dialogVisible.value = true
}

function openEdit(c: Console) {
  editingId.value = c.id
  form.value = { ...c, network_interface: c.network_interface ?? '' }
  dialogVisible.value = true
}

function onTypeChange() {
  form.value.port = DEFAULT_PORT[form.value.console_type] ?? 10023
}

const saveMutation = useMutation({
  mutationFn: () => editingId.value
    ? api.put(`/api/consoles/${editingId.value}`, form.value)
    : api.post('/api/consoles', form.value),
  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ['consoles'] })
    dialogVisible.value = false
    toast.add({ severity: 'success', summary: editingId.value ? 'Console updated' : 'Console added', life: 3000 })
  },
  onError: (err: any) => {
    toast.add({ severity: 'error', summary: 'Save failed', detail: err.response?.data?.detail ?? 'Unknown error', life: 5000 })
  },
})

const deleteMutation = useMutation({
  mutationFn: (id: number) => api.delete(`/api/consoles/${id}`),
  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ['consoles'] })
    toast.add({ severity: 'success', summary: 'Console removed', life: 3000 })
  },
})

function confirmDelete(c: Console) {
  confirm.require({
    message: `Remove console "${c.name}"?`,
    header: 'Confirm removal',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => deleteMutation.mutate(c.id),
  })
}

// ── Ping ──────────────────────────────────────────────────────
const pinging = ref<Record<number, boolean>>({})

async function doPing(c: Console) {
  pinging.value[c.id] = true
  try {
    const res = await api.post(`/api/consoles/${c.id}/ping`)
    qc.invalidateQueries({ queryKey: ['consoles'] })
    const { reachable, latency_ms } = res.data
    if (reachable) {
      toast.add({ severity: 'success', summary: `${c.name} reachable`, detail: `Latency: ${latency_ms?.toFixed(1)} ms`, life: 4000 })
    } else {
      toast.add({ severity: 'warn', summary: `${c.name} unreachable`, detail: 'No response within timeout', life: 5000 })
    }
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Ping error', detail: e.response?.data?.detail ?? 'Error', life: 4000 })
  } finally {
    pinging.value[c.id] = false
  }
}

// ── Channel Names ─────────────────────────────────────────────
const channelNamesVisible = ref(false)
const channelNamesSource = ref<Console | null>(null)
const channelNames = ref<string[]>([])
const fetchCount = ref(32)
const fetchingNames = ref(false)

function openChannelNames(c: Console) {
  channelNamesSource.value = c
  channelNames.value = []
  fetchCount.value = 32
  channelNamesVisible.value = true
}

async function fetchNames() {
  if (!channelNamesSource.value) return
  fetchingNames.value = true
  try {
    const res = await api.get(`/api/consoles/${channelNamesSource.value.id}/channels`, {
      params: { channel_count: fetchCount.value },
    })
    channelNames.value = res.data.channel_names
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Fetch failed', detail: e.response?.data?.detail ?? 'Could not reach console', life: 5000 })
  } finally {
    fetchingNames.value = false
  }
}

async function copyNames() {
  const text = channelNames.value.map((n, i) => `${i + 1}\t${n}`).join('\n')
  await navigator.clipboard.writeText(text)
  toast.add({ severity: 'success', summary: 'Copied to clipboard', life: 2000 })
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString()
}
</script>
