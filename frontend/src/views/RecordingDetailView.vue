<template>
  <AppLayout>
  <div class="p-6 max-w-6xl">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-6">
      <Button icon="pi pi-arrow-left" severity="secondary" text @click="router.push('/recordings')" />
      <div class="flex-1">
        <h1 class="text-2xl font-semibold">{{ recording?.name ?? 'Recording' }}</h1>
        <p class="text-sm text-surface-400 mt-0.5 font-mono">{{ recording?.filesystem_path }}</p>
      </div>
      <!-- Transport controls -->
      <div v-if="recording" class="flex items-center gap-2">
        <Button
          v-if="recording.status === 'pending'"
          label="Start Recording"
          icon="pi pi-circle-fill"
          severity="danger"
          :loading="transitioning"
          @click="startRecording"
        />
        <Button
          v-else-if="recording.status === 'recording'"
          label="Stop"
          icon="pi pi-stop"
          severity="secondary"
          :loading="transitioning"
          @click="stopRecording"
        />
        <Button
          v-else-if="recording.status === 'completed'"
          label="Play"
          icon="pi pi-play"
          severity="info"
          :loading="transitioning"
          @click="startPlayback"
        />
        <Button
          v-else-if="recording.status === 'playback'"
          label="Stop Playback"
          icon="pi pi-stop"
          severity="secondary"
          :loading="transitioning"
          @click="stopPlayback"
        />
        <Tag :value="recording.status" :severity="statusSeverity(recording.status)" class="capitalize" />
      </div>
    </div>

    <div v-if="isLoading" class="flex justify-center py-12">
      <ProgressSpinner />
    </div>

    <div v-else-if="recording" class="flex flex-col gap-6">

      <!-- Active recording panel: duration + level meters -->
      <Transition name="slide-down">
        <div
          v-if="recording.status === 'recording' || recording.status === 'completed'"
          class="surface-card border border-surface-200 dark:border-surface-700 rounded-xl p-5"
        >
          <!-- Duration -->
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-3">
              <span v-if="recording.status === 'recording'" class="inline-block w-3 h-3 rounded-full bg-red-500 animate-pulse" />
              <span class="font-mono text-2xl font-semibold tracking-wider">
                {{ formatDuration(recording.status === 'recording' ? meterState.duration : (recording.duration_seconds ?? 0)) }}
              </span>
            </div>
            <span class="text-sm text-surface-400">{{ recording.channel_count }} channels</span>
          </div>

          <!-- Level meters (only shown while recording) -->
          <div v-if="recording.status === 'recording' && meterState.channels.length" class="overflow-x-auto">
            <div class="flex gap-1 min-w-max pb-1">
              <div
                v-for="ch in meterState.channels"
                :key="ch.channel"
                class="flex flex-col items-center gap-1"
                style="width: 28px"
              >
                <!-- Meter bar container -->
                <div class="relative w-full bg-surface-800 rounded" style="height: 120px">
                  <!-- RMS bar -->
                  <div
                    class="absolute bottom-0 w-full rounded transition-all duration-75"
                    :style="{
                      height: dbToPercent(ch.rms_db) + '%',
                      backgroundColor: dbToColour(ch.rms_db),
                      opacity: 0.85,
                    }"
                  />
                  <!-- Peak marker -->
                  <div
                    class="absolute w-full h-0.5"
                    :style="{
                      bottom: dbToPercent(ch.peak_db) + '%',
                      backgroundColor: dbToColour(ch.peak_db),
                    }"
                  />
                </div>
                <!-- Channel label -->
                <span class="text-xs text-surface-500 font-mono">{{ ch.channel }}</span>
              </div>
            </div>
            <!-- Scale labels -->
            <div class="flex justify-between text-xs text-surface-600 font-mono mt-1 px-1">
              <span>0 dB</span>
              <span>-18</span>
              <span>-90</span>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Stats grid -->
      <div class="surface-card border border-surface-200 dark:border-surface-700 rounded-xl p-5 grid grid-cols-3 gap-4 text-sm">
        <div>
          <p class="text-surface-400 mb-1">Channels</p>
          <p class="font-medium">{{ recording.channel_count }}</p>
        </div>
        <div>
          <p class="text-surface-400 mb-1">Sample Rate</p>
          <p class="font-medium">{{ (recording.sample_rate / 1000).toFixed(1) }} kHz</p>
        </div>
        <div>
          <p class="text-surface-400 mb-1">Bit Depth</p>
          <p class="font-medium">{{ recording.bit_depth }}-bit {{ recording.codec }}</p>
        </div>
        <div>
          <p class="text-surface-400 mb-1">Duration</p>
          <p class="font-medium">{{ recording.duration_seconds ? formatDuration(recording.duration_seconds) : '—' }}</p>
        </div>
        <div>
          <p class="text-surface-400 mb-1">Started</p>
          <p class="font-medium">{{ recording.started_at ? formatDatetime(recording.started_at) : '—' }}</p>
        </div>
        <div>
          <p class="text-surface-400 mb-1">Ended</p>
          <p class="font-medium">{{ recording.ended_at ? formatDatetime(recording.ended_at) : '—' }}</p>
        </div>
        <div class="col-span-3">
          <p class="text-surface-400 mb-1">Filename Pattern</p>
          <p class="font-mono text-sm">{{ recording.filename_pattern ?? '{channel}' }}</p>
        </div>
      </div>

      <!-- Channel routing table -->
      <div>
        <h2 class="text-base font-semibold mb-3">Channel Routing</h2>
        <DataTable
          :value="recording.channels"
          class="surface-card border border-surface-200 dark:border-surface-700 rounded-xl"
          stripedRows
          size="small"
        >
          <Column field="channel_number" header="Ch #" style="width: 70px" />
          <Column field="channel_name" header="Name" />
          <Column header="Source" style="width: 220px">
            <template #body="{ data }">{{ sourceName(data.source_id) }}</template>
          </Column>
          <Column field="source_channel" header="Src Ch" style="width: 90px" />
        </DataTable>
      </div>

      <!-- Metadata -->
      <div v-if="Object.keys(recording.metadata_json ?? {}).length">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-base font-semibold">Metadata</h2>
          <Button
            v-if="!editingMeta"
            label="Edit"
            icon="pi pi-pencil"
            size="small"
            severity="secondary"
            text
            @click="beginEditMeta"
          />
        </div>
        <div v-if="!editingMeta" class="surface-card border border-surface-200 dark:border-surface-700 rounded-xl p-5 grid grid-cols-2 gap-3 text-sm">
          <div v-for="(val, key) in recording.metadata_json" :key="key">
            <p class="text-surface-400 capitalize mb-0.5">{{ key }}</p>
            <p class="font-medium">{{ val }}</p>
          </div>
        </div>
        <div v-else class="surface-card border border-surface-200 dark:border-surface-700 rounded-xl p-5">
          <div class="grid grid-cols-2 gap-3 mb-4">
            <div v-for="(_, key) in metaForm" :key="key" class="flex flex-col gap-1">
              <label class="text-sm capitalize text-surface-400">{{ key }}</label>
              <InputText v-model="metaForm[key]" size="small" class="w-full" />
            </div>
          </div>
          <div class="flex justify-end gap-2">
            <Button label="Cancel" severity="secondary" text @click="editingMeta = false" />
            <Button label="Save" :loading="savingMeta" @click="saveMeta" />
          </div>
        </div>
      </div>

      <!-- Export panel (completed recordings only) -->
      <div v-if="recording.status === 'completed' || recording.status === 'playback'">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-base font-semibold">Exports</h2>
          <Button label="New Export" icon="pi pi-file-export" size="small" severity="secondary"
            @click="exportDialogVisible = true" />
        </div>

        <div v-if="exports?.length" class="space-y-2">
          <div v-for="job in exports" :key="job.id"
            class="surface-card border border-surface-200 dark:border-surface-700 rounded-xl p-4 flex items-center gap-4">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <Tag :value="job.status" :severity="exportSeverity(job.status)" class="text-xs capitalize" />
                <span class="text-sm font-mono text-surface-400">{{ job.codec }} / {{ job.container }}</span>
                <span v-if="job.interleaved" class="text-xs text-surface-500">interleaved</span>
              </div>
              <ProgressBar v-if="job.status === 'running'" :value="job.progress_pct" :show-value="false" class="h-1.5" />
              <p v-if="job.error_message" class="text-xs text-red-400 mt-1">{{ job.error_message }}</p>
              <p v-if="job.output_path && job.status === 'completed'" class="text-xs font-mono text-surface-500 mt-1 truncate">
                {{ job.output_path }}
              </p>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <span class="text-xs text-surface-500">{{ formatDatetime(job.created_at) }}</span>
              <Button icon="pi pi-trash" text rounded size="small" severity="danger"
                :disabled="job.status === 'running'"
                @click="deleteExport(job.id)" />
            </div>
          </div>
        </div>
        <p v-else class="text-surface-500 text-sm">No exports yet.</p>
      </div>
    </div>

    <!-- Export creation dialog -->
    <Dialog v-model:visible="exportDialogVisible" header="New Export" modal style="width: 28rem">
      <div class="space-y-4 py-2">
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium">Format Preset</label>
          <Select v-model="exportPresetId" :options="exportPresets ?? []"
            optionLabel="label" optionValue="id" placeholder="Select…" class="w-full"
            @change="onPresetChange" />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div class="flex flex-col gap-1.5">
            <label class="text-sm font-medium">Codec</label>
            <InputText v-model="exportForm.codec" class="w-full" size="small" />
          </div>
          <div class="flex flex-col gap-1.5">
            <label class="text-sm font-medium">Container</label>
            <InputText v-model="exportForm.container" class="w-full" size="small" />
          </div>
        </div>
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium">Channel Selection <span class="text-surface-500 font-normal">(blank = all)</span></label>
          <InputText v-model="exportChannelInput" placeholder="e.g. 1,2,3,4" class="w-full" size="small" />
        </div>
        <div class="flex items-center gap-2">
          <Checkbox v-model="exportForm.interleaved" :binary="true" inputId="interleaved" />
          <label for="interleaved" class="text-sm">Merge channels into single file</label>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="exportDialogVisible = false" />
        <Button label="Start Export" icon="pi pi-play" :loading="startingExport" @click="submitExport" />
      </template>
    </Dialog>

    <Toast />
  </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { useToast } from 'primevue/usetoast'
import { api } from '@/api/client'
import { useRecordingMeter, dbToPercent, dbToColour } from '@/composables/useRecordingMeter'
import AppLayout from '@/components/AppLayout.vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import ProgressSpinner from 'primevue/progressspinner'
import ProgressBar from 'primevue/progressbar'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'
import Checkbox from 'primevue/checkbox'
import Toast from 'primevue/toast'

interface ExportJob {
  id: number
  recording_id: number
  status: string
  codec: string
  container: string
  interleaved: boolean
  channel_selection: number[]
  progress_pct: number
  output_path: string | null
  error_message: string | null
  created_at: string
}

const router = useRouter()
const route = useRoute()
const toast = useToast()
const queryClient = useQueryClient()

const recordingId = computed(() => route.params.id as string)

const { data: recording, isLoading, refetch } = useQuery({
  queryKey: ['recording', recordingId],
  queryFn: async () => (await api.get(`/api/recordings/${recordingId.value}`)).data,
  refetchInterval: (data) => data?.status === 'recording' ? 5000 : false,
})

const { data: sources } = useQuery({
  queryKey: ['sources'],
  queryFn: async () => (await api.get('/api/sources')).data,
})

// Meter WebSocket
const { state: meterState } = useRecordingMeter(recordingId)

// Transport
const transitioning = ref(false)

async function startRecording() {
  transitioning.value = true
  try {
    const resp = await api.post(`/api/recordings/${recordingId.value}/start`)
    queryClient.setQueryData(['recording', recordingId], resp.data)
    toast.add({ severity: 'success', summary: 'Recording started', life: 3000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.response?.data?.detail ?? 'Failed to start', life: 5000 })
  } finally {
    transitioning.value = false
  }
}

async function stopRecording() {
  transitioning.value = true
  try {
    const resp = await api.post(`/api/recordings/${recordingId.value}/stop`)
    queryClient.setQueryData(['recording', recordingId], resp.data)
    toast.add({ severity: 'success', summary: 'Recording stopped', life: 3000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.response?.data?.detail ?? 'Failed to stop', life: 5000 })
  } finally {
    transitioning.value = false
  }
}

async function startPlayback() {
  transitioning.value = true
  try {
    const resp = await api.post(`/api/recordings/${recordingId.value}/playback/start`)
    queryClient.setQueryData(['recording', recordingId], resp.data)
    toast.add({ severity: 'success', summary: 'Playback started', life: 3000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.response?.data?.detail ?? 'Failed to start playback', life: 5000 })
  } finally {
    transitioning.value = false
  }
}

async function stopPlayback() {
  transitioning.value = true
  try {
    const resp = await api.post(`/api/recordings/${recordingId.value}/playback/stop`)
    queryClient.setQueryData(['recording', recordingId], resp.data)
    toast.add({ severity: 'success', summary: 'Playback stopped', life: 3000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.response?.data?.detail ?? 'Failed to stop playback', life: 5000 })
  } finally {
    transitioning.value = false
  }
}

// Metadata editing
const editingMeta = ref(false)
const savingMeta = ref(false)
const metaForm = ref<Record<string, string>>({})

function beginEditMeta() {
  metaForm.value = { ...(recording.value?.metadata_json ?? {}) }
  editingMeta.value = true
}

async function saveMeta() {
  savingMeta.value = true
  try {
    const resp = await api.put(`/api/recordings/${recordingId.value}`, { metadata: metaForm.value })
    queryClient.setQueryData(['recording', recordingId], resp.data)
    editingMeta.value = false
    toast.add({ severity: 'success', summary: 'Metadata saved', life: 3000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.response?.data?.detail ?? 'Failed', life: 4000 })
  } finally {
    savingMeta.value = false
  }
}

// ── Exports ───────────────────────────────────────────────────
const { data: exportPresets } = useQuery({
  queryKey: ['export-presets'],
  queryFn: () => api.get('/api/export-presets').then(r => r.data),
  staleTime: Infinity,
})

const { data: exports, refetch: refetchExports } = useQuery<ExportJob[]>({
  queryKey: ['exports', recordingId],
  queryFn: () => api.get(`/api/recordings/${recordingId.value}/exports`).then(r => r.data),
  refetchInterval: (data) => (data ?? []).some((j: ExportJob) => j.status === 'running') ? 2000 : false,
  enabled: computed(() => !!recording.value && ['completed', 'playback'].includes(recording.value.status)),
})

const exportDialogVisible = ref(false)
const exportPresetId = ref<string | null>(null)
const exportForm = ref({ codec: 'pcm_s24le', container: 'wav', interleaved: false })
const exportChannelInput = ref('')
const startingExport = ref(false)

function onPresetChange() {
  const preset = (exportPresets.value as any[])?.find((p: any) => p.id === exportPresetId.value)
  if (preset) {
    exportForm.value.codec = preset.codec
    exportForm.value.container = preset.container
  }
}

function exportSeverity(status: string): 'success' | 'danger' | 'info' | 'warn' | 'secondary' {
  switch (status) {
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'running': return 'info'
    case 'pending': return 'secondary'
    default: return 'secondary'
  }
}

async function submitExport() {
  startingExport.value = true
  try {
    const channel_selection = exportChannelInput.value
      ? exportChannelInput.value.split(',').map(s => parseInt(s.trim(), 10)).filter(n => !isNaN(n))
      : []
    await api.post(`/api/recordings/${recordingId.value}/exports`, {
      codec: exportForm.value.codec,
      container: exportForm.value.container,
      interleaved: exportForm.value.interleaved,
      channel_selection,
    })
    exportDialogVisible.value = false
    exportPresetId.value = null
    exportChannelInput.value = ''
    exportForm.value = { codec: 'pcm_s24le', container: 'wav', interleaved: false }
    refetchExports()
    toast.add({ severity: 'success', summary: 'Export started', life: 3000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Export failed', detail: e.response?.data?.detail, life: 5000 })
  } finally {
    startingExport.value = false
  }
}

async function deleteExport(jobId: number) {
  try {
    await api.delete(`/api/exports/${jobId}`)
    refetchExports()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Delete failed', detail: e.response?.data?.detail, life: 4000 })
  }
}

// Helpers
function sourceName(sourceId: number): string {
  const src = (sources.value as any[])?.find((s: any) => s.id === sourceId)
  return src?.name ?? `Source ${sourceId}`
}

function statusSeverity(s?: string) {
  switch (s) {
    case 'recording': return 'danger'
    case 'completed': return 'success'
    case 'playback': return 'info'
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

function formatDatetime(iso: string): string {
  return new Date(iso).toLocaleString()
}
</script>

<style scoped>
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}
.slide-down-enter-from,
.slide-down-leave-to {
  max-height: 0;
  opacity: 0;
}
.slide-down-enter-to,
.slide-down-leave-from {
  max-height: 600px;
  opacity: 1;
}
</style>
