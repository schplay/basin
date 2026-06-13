<script setup lang="ts">
import { ref } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'
import AppLayout from '@/components/AppLayout.vue'
import { api } from '@/api/client'
import { useMonitor } from '@/composables/useMonitor'

interface Source {
  id: number
  name: string
  network_interface: string
  multicast_address: string
  channel_count: number
  sample_rate: number
  bit_depth: number
  alsa_device: string
  is_active: boolean
}

interface SourceStatus {
  source_id: number
  stream_locked: boolean
  alsa_present: boolean
  detected_channels: number | null
  detected_sample_rate: number | null
}

const qc = useQueryClient()
const toast = useToast()
const confirm = useConfirm()

const { data: sources, isPending } = useQuery<Source[]>({
  queryKey: ['sources'],
  queryFn: () => api.get('/api/sources').then(r => r.data),
  refetchInterval: 10_000,
})

const statusCache = ref<Record<number, SourceStatus>>({})

async function fetchStatus(source: Source) {
  try {
    const res = await api.get<SourceStatus>(`/api/sources/${source.id}/status`)
    statusCache.value[source.id] = res.data
  } catch { /* ignore */ }
}

const { data: sourcesWithStatus } = useQuery<Source[]>({
  queryKey: ['sources'],
  queryFn: () => api.get('/api/sources').then(r => {
    const list: Source[] = r.data
    list.forEach(fetchStatus)
    return list
  }),
  refetchInterval: 10_000,
})

// ── Dialog state ──────────────────────────────────────────────
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const form = ref({
  name: '',
  network_interface: 'eth0',
  multicast_address: '',
  channel_count: 32,
  sample_rate: 48000,
  bit_depth: 24,
  alsa_device: '',
})

const sampleRateOptions = [
  { label: '44.1 kHz', value: 44100 },
  { label: '48 kHz', value: 48000 },
  { label: '88.2 kHz', value: 88200 },
  { label: '96 kHz', value: 96000 },
]

const bitDepthOptions = [
  { label: '16-bit', value: 16 },
  { label: '24-bit', value: 24 },
  { label: '32-bit', value: 32 },
]

function openAdd() {
  editingId.value = null
  form.value = { name: '', network_interface: 'eth0', multicast_address: '', channel_count: 32, sample_rate: 48000, bit_depth: 24, alsa_device: '' }
  dialogVisible.value = true
}

function openEdit(source: Source) {
  editingId.value = source.id
  form.value = { ...source }
  dialogVisible.value = true
}

const saveMutation = useMutation({
  mutationFn: () => editingId.value
    ? api.put(`/api/sources/${editingId.value}`, form.value)
    : api.post('/api/sources', form.value),
  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ['sources'] })
    dialogVisible.value = false
    toast.add({ severity: 'success', summary: editingId.value ? 'Source updated' : 'Source added', life: 3000 })
  },
  onError: (err: any) => {
    toast.add({ severity: 'error', summary: 'Save failed', detail: err.response?.data?.detail ?? 'Unknown error', life: 5000 })
  },
})

const deleteMutation = useMutation({
  mutationFn: (id: number) => api.delete(`/api/sources/${id}`),
  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ['sources'] })
    toast.add({ severity: 'success', summary: 'Source removed', life: 3000 })
  },
})

function confirmDelete(source: Source) {
  confirm.require({
    message: `Remove source "${source.name}"?`,
    header: 'Confirm removal',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => deleteMutation.mutate(source.id),
  })
}

function statusSeverity(id: number): 'success' | 'danger' | 'secondary' {
  const s = statusCache.value[id]
  if (!s) return 'secondary'
  return s.stream_locked ? 'success' : 'danger'
}

function statusLabel(id: number): string {
  const s = statusCache.value[id]
  if (!s) return 'Checking…'
  return s.stream_locked ? 'Locked' : 'No signal'
}

function formatSampleRate(hz: number) {
  return hz >= 1000 ? `${hz / 1000} kHz` : `${hz} Hz`
}

// ── Monitor ──────────────────────────────────────────────────
const monitorVisible = ref(false)
const monitoringSource = ref<Source | null>(null)
const { isMonitoring, error: monitorError, start: startMonitor, stop: stopMonitor } = useMonitor()

function openMonitor(source: Source) {
  monitoringSource.value = source
  monitorVisible.value = true
}

async function onMonitorDialogHide() {
  await stopMonitor()
  monitoringSource.value = null
}
</script>

<template>
  <AppLayout>
    <ConfirmDialog />
    <div class="p-6">
      <div class="flex items-center justify-between mb-6">
        <div>
          <h1 class="text-2xl font-bold text-gray-900 dark:text-white">AES-67 Sources</h1>
          <p class="text-gray-500 text-sm mt-0.5">Configure multicast audio streams available to recordings</p>
        </div>
        <Button label="Add source" icon="pi pi-plus" @click="openAdd" />
      </div>

      <DataTable
        :value="sources ?? []"
        :loading="isPending"
        striped-rows
        class="text-sm"
      >
        <Column field="name" header="Name" />
        <Column header="Status">
          <template #body="{ data }">
            <Tag :severity="statusSeverity(data.id)" :value="statusLabel(data.id)" />
          </template>
        </Column>
        <Column field="multicast_address" header="Multicast address" />
        <Column field="alsa_device" header="ALSA device" />
        <Column header="Channels / Rate">
          <template #body="{ data }">
            {{ data.channel_count }} ch · {{ formatSampleRate(data.sample_rate) }} / {{ data.bit_depth }}-bit
          </template>
        </Column>
        <Column field="network_interface" header="Interface" />
        <Column header="Actions" style="width: 8rem">
          <template #body="{ data }">
            <div class="flex gap-2">
              <Button icon="pi pi-headphones" text rounded size="small" severity="info" title="Monitor" @click="openMonitor(data)" />
              <Button icon="pi pi-pencil" text rounded size="small" @click="openEdit(data)" />
              <Button icon="pi pi-trash" text rounded size="small" severity="danger" @click="confirmDelete(data)" />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>

    <!-- Add / Edit dialog -->
    <Dialog v-model:visible="dialogVisible" :header="editingId ? 'Edit source' : 'Add AES-67 source'" modal style="width: 32rem">
      <div class="space-y-4 py-2">
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium">Name</label>
          <InputText v-model="form.name" placeholder="FOH Console" class="w-full" />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div class="flex flex-col gap-1.5">
            <label class="text-sm font-medium">Multicast address</label>
            <InputText v-model="form.multicast_address" placeholder="239.69.0.1" class="w-full" />
          </div>
          <div class="flex flex-col gap-1.5">
            <label class="text-sm font-medium">Network interface</label>
            <InputText v-model="form.network_interface" placeholder="eth0" class="w-full" />
          </div>
        </div>
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium">ALSA device</label>
          <InputText v-model="form.alsa_device" placeholder="hw:AES67_FOH,0" class="w-full" />
          <p class="text-xs text-gray-500">Assigned by the AES-67 daemon. Run <code>aplay -l</code> on the appliance to list available devices.</p>
        </div>
        <div class="grid grid-cols-3 gap-3">
          <div class="flex flex-col gap-1.5">
            <label class="text-sm font-medium">Channels</label>
            <InputNumber v-model="form.channel_count" :min="1" :max="64" class="w-full" />
          </div>
          <div class="flex flex-col gap-1.5">
            <label class="text-sm font-medium">Sample rate</label>
            <Select v-model="form.sample_rate" :options="sampleRateOptions" option-label="label" option-value="value" class="w-full" />
          </div>
          <div class="flex flex-col gap-1.5">
            <label class="text-sm font-medium">Bit depth</label>
            <Select v-model="form.bit_depth" :options="bitDepthOptions" option-label="label" option-value="value" class="w-full" />
          </div>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="dialogVisible = false" />
        <Button label="Save" :loading="saveMutation.isPending.value" @click="saveMutation.mutate()" />
      </template>
    </Dialog>

    <!-- Monitor dialog -->
    <Dialog
      v-model:visible="monitorVisible"
      :header="monitoringSource ? `Monitor: ${monitoringSource.name}` : 'Monitor'"
      modal
      style="width: 24rem"
      @hide="onMonitorDialogHide"
    >
      <div class="py-4 text-center space-y-4">
        <div v-if="monitorError" class="text-red-400 text-sm">{{ monitorError }}</div>

        <div class="flex flex-col items-center gap-3">
          <i :class="['pi text-5xl', isMonitoring ? 'pi-volume-up text-green-400 animate-pulse' : 'pi-headphones text-surface-400']" />
          <p class="text-sm text-surface-400">
            {{ isMonitoring ? 'Monitoring live audio…' : 'Click Start to begin listening in your browser.' }}
          </p>
          <p v-if="!isMonitoring" class="text-xs text-surface-500">Requires browser autoplay permission.</p>
        </div>
      </div>
      <template #footer>
        <Button label="Close" severity="secondary" @click="monitorVisible = false" />
        <Button
          v-if="!isMonitoring"
          label="Start Monitoring"
          icon="pi pi-play"
          severity="info"
          @click="monitoringSource && startMonitor(monitoringSource.id)"
        />
        <Button
          v-else
          label="Stop"
          icon="pi pi-stop"
          severity="secondary"
          @click="stopMonitor"
        />
      </template>
    </Dialog>
  </AppLayout>
</template>
