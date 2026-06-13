<template>
  <AppLayout>
    <Toast />
    <ConfirmDialog />
    <div class="p-6 max-w-6xl space-y-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-semibold">Storage</h1>
          <p class="text-surface-400 text-sm mt-0.5">Manage recording destinations and file relocations</p>
        </div>
        <Button label="Add Destination" icon="pi pi-plus" @click="openCreate" />
      </div>

      <!-- Active destination card -->
      <div v-if="activeDestination" class="surface-card border border-surface-200 dark:border-surface-700 rounded-xl p-5">
        <div class="flex items-start justify-between mb-3">
          <div>
            <div class="flex items-center gap-2 mb-1">
              <Tag value="Active" severity="success" />
              <span class="font-semibold">{{ activeDestination.name }}</span>
              <Tag :value="typeLabel(activeDestination.destination_type)" severity="secondary" class="text-xs" />
            </div>
            <p class="text-surface-400 font-mono text-sm">{{ effectivePath(activeDestination) }}</p>
          </div>
          <Button
            label="Speed Test"
            icon="pi pi-stopwatch"
            size="small"
            severity="secondary"
            :loading="speedTestingId === activeDestination.id"
            @click="runSpeedTest(activeDestination)"
          />
        </div>
        <div v-if="capacity" class="space-y-1.5">
          <div class="flex justify-between text-sm text-surface-400">
            <span>{{ capacity.used_gb }} GB used</span>
            <span>{{ capacity.free_gb }} GB free of {{ capacity.total_gb }} GB</span>
          </div>
          <ProgressBar
            :value="capacity.used_pct"
            :show-value="false"
            class="h-2"
            :pt="{ value: { class: capacity.used_pct > 90 ? 'bg-red-500' : capacity.used_pct > 75 ? 'bg-yellow-500' : 'bg-green-500' } }"
          />
        </div>
        <div v-if="activeDestination.last_speed_test_write_mbps" class="mt-3 flex gap-4 text-sm text-surface-400">
          <span>Write: <strong class="text-white">{{ activeDestination.last_speed_test_write_mbps }} MB/s</strong></span>
          <span>Read: <strong class="text-white">{{ activeDestination.last_speed_test_read_mbps }} MB/s</strong></span>
          <span>Tested: {{ formatDate(activeDestination.last_speed_test_at) }}</span>
        </div>
      </div>

      <!-- Speed test matrix -->
      <div v-if="speedTestResult" class="surface-card border border-surface-200 dark:border-surface-700 rounded-xl p-5">
        <h2 class="font-semibold mb-1">Safe recording settings</h2>
        <p class="text-xs text-surface-400 mb-4">
          Based on {{ speedTestResult.write_mbps }} MB/s write · 24-bit · 20% safety margin
          <span class="ml-3 inline-flex items-center gap-2">
            <span class="inline-block w-3 h-3 rounded bg-green-500"></span>Safe
            <span class="inline-block w-3 h-3 rounded bg-yellow-500"></span>Marginal
            <span class="inline-block w-3 h-3 rounded bg-red-500"></span>Over limit
          </span>
        </p>
        <div class="overflow-x-auto">
          <table class="text-xs w-full border-collapse">
            <thead>
              <tr>
                <th class="p-2 text-left text-surface-400 font-medium">Channels</th>
                <th v-for="rate in matrixRates" :key="rate" class="p-2 text-center text-surface-400 font-medium">
                  {{ rate >= 1000 ? `${rate / 1000}k` : rate }} Hz
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="ch in matrixChannels" :key="ch">
                <td class="p-2 font-medium">{{ ch }} ch</td>
                <td v-for="rate in matrixRates" :key="rate" class="p-1">
                  <div :class="['rounded text-center p-1.5 font-mono', cellClass(getCell(ch, rate))]">
                    {{ getCell(ch, rate)?.required_mbps ?? '?' }} MB/s
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Destinations list -->
      <div>
        <h2 class="text-sm font-semibold text-surface-400 uppercase tracking-wider mb-3">All Destinations</h2>
        <DataTable :value="destinations ?? []" :loading="isPending" stripedRows size="small"
          class="surface-card border border-surface-200 dark:border-surface-700 rounded-xl">
          <Column header="Name">
            <template #body="{ data }">
              <span class="font-medium">{{ data.name }}</span>
              <Tag v-if="data.is_active" value="Active" severity="success" class="ml-2 text-xs" />
            </template>
          </Column>
          <Column header="Type" style="width: 130px">
            <template #body="{ data }">
              <Tag :value="typeLabel(data.destination_type)" severity="secondary" class="text-xs" />
            </template>
          </Column>
          <Column header="Path / Host" style="width: 220px">
            <template #body="{ data }">
              <span class="font-mono text-xs text-surface-400">{{ effectivePath(data) }}</span>
            </template>
          </Column>
          <Column header="Mount" style="width: 90px">
            <template #body="{ data }">
              <span v-if="isNetworkType(data.destination_type)">
                <i :class="data.is_mounted ? 'pi pi-check-circle text-green-400' : 'pi pi-times-circle text-surface-500'" />
              </span>
              <span v-else class="text-surface-600 text-xs">local</span>
            </template>
          </Column>
          <Column header="Speed" style="width: 110px">
            <template #body="{ data }">
              <span v-if="data.last_speed_test_write_mbps" class="text-xs">{{ data.last_speed_test_write_mbps }} MB/s W</span>
              <span v-else class="text-surface-500 text-xs">—</span>
            </template>
          </Column>
          <Column header="Actions" style="width: 250px">
            <template #body="{ data }">
              <div class="flex flex-wrap gap-1">
                <Button v-if="!data.is_active" label="Activate" size="small" severity="secondary"
                  @click="activateMutation.mutate(data.id)" />
                <template v-if="isNetworkType(data.destination_type)">
                  <Button v-if="!data.is_mounted" label="Mount" size="small" severity="info"
                    :loading="mountingId === data.id" @click="doMount(data)" />
                  <Button v-else label="Umount" size="small" severity="secondary"
                    :loading="umountingId === data.id" @click="doUmount(data)" />
                  <Button icon="pi pi-wifi" size="small" severity="secondary" text rounded
                    title="Test connection" :loading="testingId === data.id"
                    @click="doTestConnection(data)" />
                </template>
                <Button label="Test" size="small" severity="secondary"
                  :loading="speedTestingId === data.id" @click="runSpeedTest(data)" />
              </div>
            </template>
          </Column>
        </DataTable>
      </div>

      <!-- Relocations -->
      <div>
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-sm font-semibold text-surface-400 uppercase tracking-wider">Relocations</h2>
          <Button label="New Relocation" icon="pi pi-arrows-h" size="small" severity="secondary"
            @click="relocateDialogVisible = true" />
        </div>

        <div v-if="relocations?.length" class="space-y-3">
          <div
            v-for="r in relocations"
            :key="r.id"
            class="surface-card border border-surface-200 dark:border-surface-700 rounded-xl p-4"
          >
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-3 text-sm">
                <span class="font-medium">{{ destName(r.from_destination_id) }}</span>
                <i class="pi pi-arrow-right text-surface-400" />
                <span class="font-medium">{{ destName(r.to_destination_id) }}</span>
              </div>
              <div class="flex items-center gap-3">
                <Tag :value="r.status" :severity="relocationSeverity(r.status)" class="text-xs capitalize" />
                <Button v-if="r.status === 'pending'" icon="pi pi-times" text rounded size="small"
                  severity="danger" title="Cancel" @click="cancelRelocation(r.id)" />
              </div>
            </div>
            <div v-if="r.status === 'in_progress' || r.status === 'completed'" class="space-y-1">
              <div class="flex justify-between text-xs text-surface-400">
                <span>{{ r.files_moved }} / {{ r.files_total }} files</span>
                <span>{{ formatBytes(r.bytes_moved) }} / {{ formatBytes(r.bytes_total) }}</span>
              </div>
              <ProgressBar
                :value="r.files_total ? Math.round(r.files_moved / r.files_total * 100) : 0"
                :show-value="false"
                class="h-2"
              />
            </div>
            <p class="text-xs text-surface-500 mt-1">Started {{ formatDate(r.created_at) }}</p>
          </div>
        </div>
        <p v-else class="text-surface-500 text-sm text-center py-6">No relocations yet.</p>
      </div>
    </div>

    <!-- Add / Edit destination dialog -->
    <Dialog v-model:visible="dialogVisible" :header="editingId ? 'Edit Destination' : 'Add Destination'" modal style="width: 34rem">
      <div class="space-y-4 py-2">
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium">Name</label>
          <InputText v-model="form.name" placeholder="Local NVMe" class="w-full" />
        </div>
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium">Type</label>
          <Select v-model="form.destination_type" :options="typeOptions" option-label="label"
            option-value="value" class="w-full" :disabled="!!editingId" />
        </div>

        <!-- Local fields -->
        <template v-if="form.destination_type === 'local_os' || form.destination_type === 'local_volume'">
          <div class="flex flex-col gap-1.5">
            <label class="text-sm font-medium">Local Path</label>
            <InputText v-model="form.local_path" placeholder="/mnt/recordings" class="w-full" />
            <p class="text-xs text-surface-400">Will be created if it does not exist.</p>
          </div>
        </template>

        <!-- Network shared fields -->
        <template v-if="form.destination_type === 'network_smb' || form.destination_type === 'network_nfs'">
          <div class="grid grid-cols-2 gap-3">
            <div class="flex flex-col gap-1.5">
              <label class="text-sm font-medium">Host</label>
              <InputText v-model="form.network_host" placeholder="192.168.1.50" class="w-full" />
            </div>
            <div class="flex flex-col gap-1.5">
              <label class="text-sm font-medium">Share / Export Path</label>
              <InputText v-model="form.network_share" placeholder="recordings" class="w-full" />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div class="flex flex-col gap-1.5">
              <label class="text-sm font-medium">Mount Point</label>
              <InputText v-model="form.mount_point" placeholder="/mnt/basin-storage" class="w-full" />
            </div>
            <div class="flex flex-col gap-1.5">
              <label class="text-sm font-medium">Network Interface</label>
              <InputText v-model="form.network_interface" placeholder="eth0" class="w-full" />
            </div>
          </div>
        </template>

        <!-- SMB-specific fields -->
        <template v-if="form.destination_type === 'network_smb'">
          <div class="grid grid-cols-2 gap-3">
            <div class="flex flex-col gap-1.5">
              <label class="text-sm font-medium">Username</label>
              <InputText v-model="form.smb_username" placeholder="nas-user" class="w-full" />
            </div>
            <div class="flex flex-col gap-1.5">
              <label class="text-sm font-medium">Password</label>
              <InputText v-model="form.smb_password" type="password" placeholder="••••••••" class="w-full" />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div class="flex flex-col gap-1.5">
              <label class="text-sm font-medium">Domain <span class="text-surface-500 font-normal">(optional)</span></label>
              <InputText v-model="form.smb_domain" placeholder="WORKGROUP" class="w-full" />
            </div>
            <div class="flex flex-col gap-1.5">
              <label class="text-sm font-medium">SMB Version</label>
              <Select v-model="form.smb_version" :options="smbVersionOptions" option-label="label"
                option-value="value" class="w-full" />
            </div>
          </div>
        </template>

        <!-- NFS-specific fields -->
        <template v-if="form.destination_type === 'network_nfs'">
          <div class="grid grid-cols-2 gap-3">
            <div class="flex flex-col gap-1.5">
              <label class="text-sm font-medium">NFS Version</label>
              <Select v-model="form.nfs_version" :options="nfsVersionOptions" option-label="label"
                option-value="value" class="w-full" />
            </div>
            <div class="flex flex-col gap-1.5">
              <label class="text-sm font-medium">Extra Options <span class="text-surface-500 font-normal">(optional)</span></label>
              <InputText v-model="form.nfs_options" placeholder="rsize=1048576,wsize=1048576" class="w-full" />
            </div>
          </div>
        </template>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="dialogVisible = false" />
        <Button label="Save" :loading="saveMutation.isPending.value" @click="saveMutation.mutate()" />
      </template>
    </Dialog>

    <!-- New relocation dialog -->
    <Dialog v-model:visible="relocateDialogVisible" header="New Relocation Job" modal style="width: 28rem">
      <div class="space-y-4 py-2">
        <p class="text-sm text-surface-400">
          All recordings will be copied from the source to the target destination.
          Source files will be deleted after a successful copy.
        </p>
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium">From (source)</label>
          <Select v-model="relocForm.from_destination_id" :options="destinations ?? []"
            optionLabel="name" optionValue="id" placeholder="Select source…" class="w-full" />
        </div>
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium">To (target)</label>
          <Select v-model="relocForm.to_destination_id" :options="destinations ?? []"
            optionLabel="name" optionValue="id" placeholder="Select target…" class="w-full" />
        </div>
        <div class="flex items-center gap-2">
          <Checkbox v-model="relocForm.delete_source" :binary="true" inputId="del_src" />
          <label for="del_src" class="text-sm">Delete source files after copy</label>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="relocateDialogVisible = false" />
        <Button
          label="Start Relocation"
          icon="pi pi-play"
          :loading="startingReloc"
          :disabled="!relocForm.from_destination_id || !relocForm.to_destination_id"
          @click="submitRelocation"
        />
      </template>
    </Dialog>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { api } from '@/api/client'
import AppLayout from '@/components/AppLayout.vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import ProgressBar from 'primevue/progressbar'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Checkbox from 'primevue/checkbox'
import ConfirmDialog from 'primevue/confirmdialog'
import Toast from 'primevue/toast'

interface Destination {
  id: number
  name: string
  destination_type: string
  is_active: boolean
  local_path: string | null
  network_host: string | null
  network_share: string | null
  mount_point: string | null
  smb_username: string | null
  smb_domain: string | null
  smb_version: string | null
  nfs_version: string | null
  nfs_options: string | null
  is_mounted: boolean
  last_speed_test_at: string | null
  last_speed_test_write_mbps: number | null
  last_speed_test_read_mbps: number | null
}

interface Relocation {
  id: number
  from_destination_id: number
  to_destination_id: number
  status: string
  files_total: number
  files_moved: number
  bytes_total: number
  bytes_moved: number
  celery_task_id: string | null
  created_at: string
}

const qc = useQueryClient()
const toast = useToast()
const confirm = useConfirm()

const hasActiveRelocation = computed(() => relocations.value?.some(r => r.status === 'in_progress'))

const { data: destinations, isPending } = useQuery<Destination[]>({
  queryKey: ['storage-destinations'],
  queryFn: () => api.get('/api/storage/destinations').then(r => r.data),
  refetchInterval: 15_000,
})

const { data: relocations } = useQuery<Relocation[]>({
  queryKey: ['storage-relocations'],
  queryFn: () => api.get('/api/storage/relocations').then(r => r.data),
  refetchInterval: computed(() => hasActiveRelocation.value ? 2000 : 15_000),
})

const activeDestination = computed(() => destinations.value?.find(d => d.is_active) ?? null)

const { data: capacity } = useQuery({
  queryKey: ['storage-capacity'],
  queryFn: () => activeDestination.value
    ? api.get(`/api/storage/destinations/${activeDestination.value.id}/capacity`).then(r => r.data)
    : Promise.resolve(null),
  enabled: computed(() => !!activeDestination.value),
  refetchInterval: 30_000,
})

// ── Constants ─────────────────────────────────────────────────
const typeOptions = [
  { label: 'Local OS path', value: 'local_os' },
  { label: 'Local volume (separately mounted)', value: 'local_volume' },
  { label: 'Network share (SMB/CIFS)', value: 'network_smb' },
  { label: 'Network share (NFS)', value: 'network_nfs' },
]

const smbVersionOptions = [
  { label: 'Auto', value: 'auto' },
  { label: 'SMB 3.0', value: '3.0' },
  { label: 'SMB 2.1', value: '2.1' },
  { label: 'SMB 2.0', value: '2.0' },
  { label: 'SMB 1.0 (legacy)', value: '1.0' },
]

const nfsVersionOptions = [
  { label: 'NFSv4 (recommended)', value: '4' },
  { label: 'NFSv3', value: '3' },
  { label: 'NFSv4.1', value: '4.1' },
]

const matrixChannels = [8, 16, 24, 32, 48, 64]
const matrixRates = [44100, 48000, 88200, 96000]

// ── Add / Edit dialog ─────────────────────────────────────────
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const form = ref({
  name: '', destination_type: 'local_os', local_path: '',
  network_host: '', network_share: '', network_interface: '',
  mount_point: '/mnt/basin-storage',
  smb_username: '', smb_password: '', smb_domain: '', smb_version: '3.0',
  nfs_version: '4', nfs_options: '',
})

function openCreate() {
  editingId.value = null
  form.value = { name: '', destination_type: 'local_os', local_path: '', network_host: '', network_share: '',
    network_interface: '', mount_point: '/mnt/basin-storage', smb_username: '', smb_password: '',
    smb_domain: '', smb_version: '3.0', nfs_version: '4', nfs_options: '' }
  dialogVisible.value = true
}

function openEdit(d: Destination) {
  editingId.value = d.id
  form.value = {
    name: d.name, destination_type: d.destination_type, local_path: d.local_path ?? '',
    network_host: d.network_host ?? '', network_share: d.network_share ?? '',
    network_interface: '', mount_point: d.mount_point ?? '/mnt/basin-storage',
    smb_username: d.smb_username ?? '', smb_password: '', smb_domain: d.smb_domain ?? '',
    smb_version: d.smb_version ?? '3.0', nfs_version: d.nfs_version ?? '4', nfs_options: d.nfs_options ?? '',
  }
  dialogVisible.value = true
}

const saveMutation = useMutation({
  mutationFn: () => editingId.value
    ? api.put(`/api/storage/destinations/${editingId.value}`, form.value)
    : api.post('/api/storage/destinations', form.value),
  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ['storage-destinations'] })
    dialogVisible.value = false
    toast.add({ severity: 'success', summary: editingId.value ? 'Destination updated' : 'Destination added', life: 3000 })
  },
  onError: (err: any) => {
    toast.add({ severity: 'error', summary: 'Save failed', detail: err.response?.data?.detail ?? 'Unknown error', life: 5000 })
  },
})

// ── Activate ──────────────────────────────────────────────────
const activateMutation = useMutation({
  mutationFn: (id: number) => api.post(`/api/storage/destinations/${id}/activate`),
  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ['storage-destinations'] })
    qc.invalidateQueries({ queryKey: ['storage-capacity'] })
    toast.add({ severity: 'success', summary: 'Active destination updated', life: 3000 })
  },
  onError: (err: any) => {
    toast.add({ severity: 'error', summary: 'Activation failed', detail: err.response?.data?.detail, life: 5000 })
  },
})

// ── Speed test ────────────────────────────────────────────────
const speedTestingId = ref<number | null>(null)
const speedTestResult = ref<any | null>(null)

async function runSpeedTest(dest: Destination) {
  speedTestingId.value = dest.id
  speedTestResult.value = null
  try {
    const res = await api.post(`/api/storage/destinations/${dest.id}/test`)
    speedTestResult.value = res.data
    qc.invalidateQueries({ queryKey: ['storage-destinations'] })
    toast.add({ severity: 'success', summary: 'Speed test complete', life: 3000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Speed test failed', detail: err.response?.data?.detail ?? 'Unknown error', life: 5000 })
  } finally {
    speedTestingId.value = null
  }
}

function getCell(channels: number, rate: number) {
  return speedTestResult.value?.safe_settings?.find((s: any) => s.channels === channels && s.sample_rate === rate)
}
function cellClass(cell: any) {
  if (!cell) return 'bg-surface-800'
  if (cell.safe) return 'bg-green-900/40 text-green-300'
  if (cell.marginal) return 'bg-yellow-900/40 text-yellow-300'
  return 'bg-red-900/40 text-red-300'
}

// ── Network operations ────────────────────────────────────────
const mountingId = ref<number | null>(null)
const umountingId = ref<number | null>(null)
const testingId = ref<number | null>(null)

async function doMount(dest: Destination) {
  mountingId.value = dest.id
  try {
    await api.post(`/api/storage/destinations/${dest.id}/mount`)
    qc.invalidateQueries({ queryKey: ['storage-destinations'] })
    toast.add({ severity: 'success', summary: `${dest.name} mounted`, life: 3000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Mount failed', detail: err.response?.data?.detail, life: 6000 })
  } finally {
    mountingId.value = null
  }
}

async function doUmount(dest: Destination) {
  umountingId.value = dest.id
  try {
    await api.post(`/api/storage/destinations/${dest.id}/umount`)
    qc.invalidateQueries({ queryKey: ['storage-destinations'] })
    toast.add({ severity: 'success', summary: `${dest.name} unmounted`, life: 3000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Unmount failed', detail: err.response?.data?.detail, life: 6000 })
  } finally {
    umountingId.value = null
  }
}

async function doTestConnection(dest: Destination) {
  testingId.value = dest.id
  try {
    const res = await api.post(`/api/storage/destinations/${dest.id}/test-connection`)
    const { ok, detail } = res.data
    toast.add({ severity: ok ? 'success' : 'warn', summary: ok ? 'Connection OK' : 'Connection failed', detail, life: 5000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Test failed', detail: err.response?.data?.detail, life: 5000 })
  } finally {
    testingId.value = null
  }
}

// ── Relocations ───────────────────────────────────────────────
const relocateDialogVisible = ref(false)
const startingReloc = ref(false)
const relocForm = ref({ from_destination_id: null as number | null, to_destination_id: null as number | null, delete_source: true })

async function submitRelocation() {
  startingReloc.value = true
  try {
    await api.post('/api/storage/relocations', relocForm.value)
    qc.invalidateQueries({ queryKey: ['storage-relocations'] })
    relocateDialogVisible.value = false
    toast.add({ severity: 'success', summary: 'Relocation started', life: 3000 })
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Failed', detail: err.response?.data?.detail, life: 5000 })
  } finally {
    startingReloc.value = false
  }
}

function cancelRelocation(id: number) {
  confirm.require({
    message: 'Cancel this relocation job?',
    header: 'Confirm',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      await api.delete(`/api/storage/relocations/${id}`)
      qc.invalidateQueries({ queryKey: ['storage-relocations'] })
    },
  })
}

// ── Helpers ───────────────────────────────────────────────────
function isNetworkType(t: string) { return t === 'network_smb' || t === 'network_nfs' }

function effectivePath(d: Destination) {
  if (isNetworkType(d.destination_type)) {
    const share = d.destination_type === 'network_smb'
      ? `//${d.network_host}/${d.network_share}`
      : `${d.network_host}:${d.network_share}`
    return `${share}  →  ${d.mount_point ?? '/mnt/basin-storage'}`
  }
  return d.local_path ?? '—'
}

function typeLabel(t: string) {
  const map: Record<string, string> = {
    local_os: 'Local OS', local_volume: 'Volume', network_smb: 'SMB', network_nfs: 'NFS',
  }
  return map[t] ?? t
}

function destName(id: number) {
  return destinations.value?.find(d => d.id === id)?.name ?? `Dest ${id}`
}

function relocationSeverity(s: string) {
  switch (s) {
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'in_progress': return 'warn'
    default: return 'secondary'
  }
}

function formatDate(iso: string | null) { return iso ? new Date(iso).toLocaleString() : '—' }

function formatBytes(b: number) {
  if (b >= 1e12) return (b / 1e12).toFixed(1) + ' TB'
  if (b >= 1e9) return (b / 1e9).toFixed(1) + ' GB'
  if (b >= 1e6) return (b / 1e6).toFixed(0) + ' MB'
  return b + ' B'
}
</script>
