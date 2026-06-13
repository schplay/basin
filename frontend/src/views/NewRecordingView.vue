<template>
  <AppLayout>
  <div class="p-6 max-w-4xl">
    <div class="flex items-center gap-3 mb-6">
      <Button icon="pi pi-arrow-left" severity="secondary" text @click="router.back()" />
      <h1 class="text-2xl font-semibold">New Recording</h1>
    </div>

    <Stepper v-model:value="step" linear>
      <!-- Step 1: Basic info -->
      <StepList>
        <Step value="1">Setup</Step>
        <Step value="2">Channels</Step>
        <Step value="3">Metadata</Step>
      </StepList>

      <StepPanels>
        <!-- STEP 0: Setup -->
        <StepPanel value="1">
          <div class="flex flex-col gap-5 py-4 max-w-lg">
            <div class="flex flex-col gap-1">
              <label class="text-sm font-medium">Recording Name *</label>
              <InputText v-model="form.name" class="w-full" placeholder="e.g. Night 1" autofocus />
            </div>

            <div class="flex flex-col gap-1">
              <label class="text-sm font-medium">Group *</label>
              <TreeSelect
                v-model="selectedGroup"
                :options="groupTreeNodes"
                selectionMode="single"
                placeholder="Select a group"
                class="w-full"
                :loading="groupsLoading"
              />
            </div>

            <div class="flex flex-col gap-1">
              <label class="text-sm font-medium">Template <span class="text-surface-400 font-normal">(optional)</span></label>
              <Select
                v-model="form.template_id"
                :options="templates ?? []"
                optionLabel="name"
                optionValue="id"
                placeholder="None — configure channels manually"
                :loading="templatesLoading"
                class="w-full"
                showClear
                @change="onTemplateChange"
              />
            </div>

            <div class="flex flex-col gap-1">
              <label class="text-sm font-medium">Channel Count *</label>
              <InputNumber v-model="form.channel_count" :min="1" :max="64" class="w-full" @update:modelValue="resizeChannels" />
              <span class="text-xs text-surface-400">Set before proceeding — changing later resets routing</span>
            </div>

            <div class="grid grid-cols-3 gap-3">
              <div class="flex flex-col gap-1">
                <label class="text-sm font-medium">Sample Rate</label>
                <Select v-model="form.sample_rate" :options="SAMPLE_RATES" optionLabel="label" optionValue="value" class="w-full" />
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-sm font-medium">Bit Depth</label>
                <Select v-model="form.bit_depth" :options="BIT_DEPTHS" optionLabel="label" optionValue="value" class="w-full" />
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-sm font-medium">Container</label>
                <Select v-model="form.container" :options="CONTAINERS" optionLabel="label" optionValue="value" class="w-full" />
              </div>
            </div>

            <div class="flex flex-col gap-1">
              <label class="text-sm font-medium">Channel Filename Pattern
                <span class="text-surface-400 font-normal">(optional)</span>
              </label>
              <InputText v-model="form.filename_pattern" class="w-full font-mono"
                placeholder="{channel}  or  {date}_{channel}  or  show_{date}_{time}_{channel}" />
              <p class="text-xs text-surface-500">
                Tokens: <code class="font-mono">{channel}</code> (001…),
                <code class="font-mono">{date}</code> (YYYYMMDD),
                <code class="font-mono">{time}</code> (HHMMSS),
                <code class="font-mono">{datetime}</code> (YYYYMMDD_HHMMSS).
                Leave blank for <code class="font-mono">{channel}</code>.
              </p>
              <p v-if="form.filename_pattern.trim()" class="text-xs font-mono text-primary-400">
                Preview: {{ previewFilename(form.filename_pattern) }}
              </p>
            </div>
          </div>

          <div class="flex justify-end mt-4">
            <Button label="Next: Channels" icon="pi pi-arrow-right" iconPos="right" :disabled="!canProceedFromStep0" @click="step = '2'" />
          </div>
        </StepPanel>

        <!-- STEP 1: Channel routing -->
        <StepPanel value="2">
          <div class="py-4">
            <div class="flex flex-wrap items-center justify-between gap-3 mb-3">
              <p class="text-sm text-surface-400">Assign a source and source channel for each recording channel.</p>
              <div class="flex items-center gap-3 flex-wrap">
                <!-- Import channel names from console -->
                <div class="flex items-center gap-2">
                  <label class="text-sm text-surface-400">Import names:</label>
                  <Select
                    v-model="importConsoleId"
                    :options="consoles ?? []"
                    optionLabel="name"
                    optionValue="id"
                    placeholder="From console…"
                    size="small"
                    class="w-40"
                  />
                  <Button
                    icon="pi pi-download"
                    size="small"
                    severity="secondary"
                    :disabled="!importConsoleId"
                    :loading="importingNames"
                    title="Fetch channel names from console"
                    @click="importNamesFromConsole"
                  />
                </div>
                <!-- Bulk source assign -->
                <div class="flex items-center gap-2">
                  <label class="text-sm text-surface-400">Source to all:</label>
                  <Select
                    v-model="bulkSource"
                    :options="sources ?? []"
                    optionLabel="name"
                    optionValue="id"
                    placeholder="Select..."
                    size="small"
                    class="w-44"
                    :loading="sourcesLoading"
                    @change="applyBulkSource"
                  />
                </div>
              </div>
            </div>

            <div class="border border-surface-200 dark:border-surface-700 rounded-lg overflow-hidden">
              <div class="max-h-[420px] overflow-y-auto">
                <table class="w-full text-sm">
                  <thead class="sticky top-0 surface-100 dark:bg-surface-800 z-10">
                    <tr>
                      <th class="text-left px-3 py-2 w-12 text-surface-500">Ch</th>
                      <th class="text-left px-3 py-2 text-surface-500">Name</th>
                      <th class="text-left px-3 py-2 w-52 text-surface-500">Source</th>
                      <th class="text-left px-3 py-2 w-28 text-surface-500">Src Ch</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="(ch, idx) in form.channels"
                      :key="idx"
                      class="border-t border-surface-100 dark:border-surface-700"
                      :class="{ 'bg-red-500/5': !ch.source_id }"
                    >
                      <td class="px-3 py-1 text-surface-400 font-mono text-xs">{{ idx + 1 }}</td>
                      <td class="px-2 py-1">
                        <InputText v-model="ch.channel_name" size="small" class="w-full" :placeholder="`Ch ${idx + 1}`" />
                      </td>
                      <td class="px-2 py-1">
                        <Select
                          v-model="ch.source_id"
                          :options="sources ?? []"
                          optionLabel="name"
                          optionValue="id"
                          placeholder="Pick source"
                          size="small"
                          class="w-full"
                          @change="() => clampSourceChannel(idx)"
                        />
                      </td>
                      <td class="px-2 py-1">
                        <InputNumber
                          v-model="ch.source_channel"
                          :min="1"
                          :max="sourceChannelMax(ch.source_id)"
                          size="small"
                          class="w-full"
                          :disabled="!ch.source_id"
                        />
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <p v-if="unassignedCount > 0" class="text-sm text-red-400 mt-2">
              {{ unassignedCount }} channel{{ unassignedCount > 1 ? 's' : '' }} still need a source assigned
            </p>
          </div>

          <div class="flex justify-between mt-4">
            <Button label="Back" icon="pi pi-arrow-left" severity="secondary" text @click="step = '1'" />
            <Button label="Next: Metadata" icon="pi pi-arrow-right" iconPos="right" :disabled="unassignedCount > 0" @click="step = '3'" />
          </div>
        </StepPanel>

        <!-- STEP 2: Metadata -->
        <StepPanel value="3">
          <div class="grid grid-cols-2 gap-4 py-4 max-w-xl">
            <div v-for="field in METADATA_FIELDS" :key="field.key" class="flex flex-col gap-1">
              <label class="text-sm font-medium">{{ field.label }}</label>
              <InputText v-model="form.metadata[field.key]" class="w-full" :placeholder="field.placeholder" />
            </div>
            <div class="col-span-2 flex flex-col gap-1">
              <label class="text-sm font-medium">Notes</label>
              <Textarea v-model="form.metadata.notes" rows="3" class="w-full" placeholder="Any additional notes..." />
            </div>
          </div>

          <!-- Preview -->
          <div class="surface-50 dark:bg-surface-800 rounded-lg p-4 mb-4 text-sm font-mono text-surface-400 max-w-xl">
            <p class="text-xs uppercase tracking-wider text-surface-500 mb-2">Recording directory</p>
            <p class="break-all text-surface-300">
              &lt;storage-root&gt;/{{ selectedGroupPath }}/{{ sanitizeName(form.name) || '…' }}
            </p>
          </div>

          <div class="flex justify-between mt-4">
            <Button label="Back" icon="pi pi-arrow-left" severity="secondary" text @click="step = '2'" />
            <Button label="Create Recording" icon="pi pi-check" :loading="creating" @click="submitRecording" />
          </div>
        </StepPanel>
      </StepPanels>
    </Stepper>

    <Toast />
  </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { useToast } from 'primevue/usetoast'
import { api } from '@/api/client'
import AppLayout from '@/components/AppLayout.vue'
import Stepper from 'primevue/stepper'
import StepList from 'primevue/steplist'
import Step from 'primevue/step'
import StepPanels from 'primevue/steppanels'
import StepPanel from 'primevue/steppanel'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import TreeSelect from 'primevue/treeselect'
import Textarea from 'primevue/textarea'
import Toast from 'primevue/toast'

const router = useRouter()
const toast = useToast()
const step = ref<string>('1')

// Data
const { data: groups, isLoading: groupsLoading } = useQuery({
  queryKey: ['groups'],
  queryFn: async () => (await api.get('/api/groups')).data,
})

const { data: templates, isLoading: templatesLoading } = useQuery({
  queryKey: ['templates'],
  queryFn: async () => (await api.get('/api/templates')).data,
})

const { data: sources, isLoading: sourcesLoading } = useQuery({
  queryKey: ['sources'],
  queryFn: async () => (await api.get('/api/sources')).data,
})

const { data: consoles } = useQuery({
  queryKey: ['consoles'],
  queryFn: async () => (await api.get('/api/consoles')).data,
})

// Constants
const SAMPLE_RATES = [
  { label: '44.1 kHz', value: 44100 },
  { label: '48 kHz', value: 48000 },
  { label: '88.2 kHz', value: 88200 },
  { label: '96 kHz', value: 96000 },
]
const BIT_DEPTHS = [
  { label: '16-bit', value: 16 },
  { label: '24-bit', value: 24 },
  { label: '32-bit float', value: 32 },
]
const CONTAINERS = [
  { label: 'WAV', value: 'wav' },
  { label: 'AIFF', value: 'aiff' },
  { label: 'RF64', value: 'rf64' },
]
const METADATA_FIELDS = [
  { key: 'artist', label: 'Artist / Performer', placeholder: 'The Band' },
  { key: 'venue', label: 'Venue', placeholder: 'Main Stage' },
  { key: 'engineer', label: 'Engineer', placeholder: 'John Smith' },
  { key: 'project', label: 'Project', placeholder: 'Summer Tour 2024' },
  { key: 'date', label: 'Date', placeholder: '2024-07-04' },
  { key: 'city', label: 'City', placeholder: 'New York' },
]

// Form
interface ChannelRow {
  channel_number: number
  source_id: number | null
  source_channel: number
  channel_name: string
}

const form = reactive({
  name: '',
  group_id: null as number | null,
  template_id: null as number | null,
  channel_count: 8,
  sample_rate: 48000,
  bit_depth: 24,
  codec: 'pcm_s24le',
  container: 'wav',
  channels: [] as ChannelRow[],
  metadata: {} as Record<string, string>,
  filename_pattern: '',
})

const selectedGroup = ref<Record<string, any>>({})
const bulkSource = ref<number | null>(null)
const importConsoleId = ref<number | null>(null)
const importingNames = ref(false)
const creating = ref(false)

// Group tree for TreeSelect
function toTreeNodes(groups: any[]): any[] {
  return (groups ?? []).map(g => ({
    key: String(g.id),
    label: g.name,
    data: g,
    children: toTreeNodes(g.children ?? []),
    selectable: true,
  }))
}
const groupTreeNodes = computed(() => toTreeNodes(groups.value ?? []))

const selectedGroupId = computed<number | null>(() => {
  const keys = Object.keys(selectedGroup.value)
  return keys.length ? parseInt(keys[0]) : null
})

const selectedGroupPath = computed<string>(() => {
  if (!selectedGroupId.value || !groups.value) return '…'
  function find(list: any[]): string | null {
    for (const g of list) {
      if (g.id === selectedGroupId.value) return g.filesystem_path
      const found = find(g.children ?? [])
      if (found) return found
    }
    return null
  }
  return find(groups.value) ?? '…'
})

// Initialise channels when count changes
function resizeChannels(count: number) {
  const existing = form.channels.slice(0, count)
  while (existing.length < count) {
    const idx = existing.length
    existing.push({
      channel_number: idx + 1,
      source_id: null,
      source_channel: idx + 1,
      channel_name: `Ch ${idx + 1}`,
    })
  }
  existing.forEach((ch, i) => { ch.channel_number = i + 1 })
  form.channels = existing
}

resizeChannels(form.channel_count)

function onTemplateChange() {
  if (!form.template_id || !templates.value) return
  const tmpl = (templates.value as any[]).find((t: any) => t.id === form.template_id)
  if (!tmpl) return
  form.channel_count = tmpl.channel_count
  // Reinitialise channels with template names
  form.channels = Array.from({ length: tmpl.channel_count }, (_, i) => ({
    channel_number: i + 1,
    source_id: tmpl.channel_source_defaults?.[i]?.source_id ?? null,
    source_channel: tmpl.channel_source_defaults?.[i]?.source_channel ?? i + 1,
    channel_name: tmpl.channel_names?.[i] ?? `Ch ${i + 1}`,
  }))
  // Apply template metadata defaults and filename pattern
  form.metadata = { ...tmpl.metadata_defaults }
  form.filename_pattern = tmpl.filename_pattern ?? ''
}

function sourceChannelMax(sourceId: number | null): number {
  if (!sourceId || !sources.value) return 64
  const src = (sources.value as any[]).find((s: any) => s.id === sourceId)
  return src?.channel_count ?? 64
}

function clampSourceChannel(idx: number) {
  const ch = form.channels[idx]
  const max = sourceChannelMax(ch.source_id)
  if (ch.source_channel > max) ch.source_channel = max
}

async function importNamesFromConsole() {
  if (!importConsoleId.value) return
  importingNames.value = true
  try {
    const resp = await api.get(`/api/consoles/${importConsoleId.value}/channels`, {
      params: { channel_count: form.channel_count },
    })
    const names: string[] = resp.data.channel_names
    form.channels.forEach((ch, i) => {
      if (names[i]) ch.channel_name = names[i]
    })
    toast.add({ severity: 'success', summary: 'Channel names imported', life: 3000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Import failed', detail: e.response?.data?.detail ?? 'Could not reach console', life: 5000 })
  } finally {
    importingNames.value = false
  }
}

function applyBulkSource() {
  if (!bulkSource.value) return
  form.channels.forEach((ch) => {
    ch.source_id = bulkSource.value
    const max = sourceChannelMax(bulkSource.value)
    if (ch.source_channel > max) ch.source_channel = max
  })
}

const unassignedCount = computed(() => form.channels.filter(ch => !ch.source_id).length)

const canProceedFromStep0 = computed(
  () => form.name.trim() && selectedGroupId.value && form.channel_count >= 1,
)

function sanitizeName(name: string): string {
  return name.trim().replace(/[/\\:*?"<>|]/g, '-').replace(/\s{2,}/g, ' ')
}

function previewFilename(pattern: string): string {
  const now = new Date()
  const pad = (n: number, l = 2) => String(n).padStart(l, '0')
  const date = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`
  const time = `${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
  const ext = form.container === 'aiff' ? '.aif' : `.${form.container}`
  return (pattern || '{channel}')
    .replace(/\{channel\}/g, '001')
    .replace(/\{datetime\}/g, `${date}_${time}`)
    .replace(/\{date\}/g, date)
    .replace(/\{time\}/g, time) + ext
}

async function submitRecording() {
  if (!selectedGroupId.value) return
  creating.value = true
  try {
    const payload = {
      name: form.name.trim(),
      group_id: selectedGroupId.value,
      template_id: form.template_id,
      channels: form.channels.map(ch => ({
        channel_number: ch.channel_number,
        source_id: ch.source_id,
        source_channel: ch.source_channel,
        channel_name: ch.channel_name,
      })),
      sample_rate: form.sample_rate,
      bit_depth: form.bit_depth,
      codec: form.codec,
      container: form.container,
      metadata: form.metadata,
      filename_pattern: form.filename_pattern.trim() || null,
    }
    const resp = await api.post('/api/recordings', payload)
    toast.add({ severity: 'success', summary: 'Recording created', life: 3000 })
    router.push(`/recordings/${resp.data.id}`)
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.response?.data?.detail ?? 'Failed to create recording', life: 5000 })
  } finally {
    creating.value = false
  }
}
</script>
