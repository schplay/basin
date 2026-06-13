<template>
  <AppLayout>
  <div class="p-6 max-w-5xl">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-semibold">Recording Templates</h1>
      <Button label="New Template" icon="pi pi-plus" @click="openCreate" />
    </div>

    <div v-if="isLoading" class="flex justify-center py-12">
      <ProgressSpinner />
    </div>

    <div v-else-if="!templates?.length" class="text-center py-16 text-surface-400">
      <i class="pi pi-copy text-5xl mb-4 block" />
      <p class="text-lg mb-2">No templates yet</p>
      <p class="text-sm mb-6">Templates define channel counts, names, and default routing for recordings</p>
      <Button label="Create First Template" icon="pi pi-plus" @click="openCreate" />
    </div>

    <DataTable v-else :value="templates" class="surface-card rounded-xl border border-surface-200 dark:border-surface-700" stripedRows>
      <Column field="name" header="Name" sortable />
      <Column field="channel_count" header="Channels" style="width: 100px" />
      <Column field="sample_rate" header="Sample Rate" style="width: 130px">
        <template #body="{ data }">{{ (data.sample_rate / 1000).toFixed(1) }} kHz</template>
      </Column>
      <Column field="bit_depth" header="Bit Depth" style="width: 110px">
        <template #body="{ data }">{{ data.bit_depth }}-bit</template>
      </Column>
      <Column field="container" header="Format" style="width: 100px">
        <template #body="{ data }">{{ data.container.toUpperCase() }}</template>
      </Column>
      <Column header="Actions" style="width: 120px">
        <template #body="{ data }">
          <div class="flex gap-1">
            <Button icon="pi pi-pencil" size="small" severity="secondary" text @click="openEdit(data)" />
            <Button icon="pi pi-trash" size="small" severity="danger" text @click="confirmDelete(data)" />
          </div>
        </template>
      </Column>
    </DataTable>

    <!-- Create/Edit dialog -->
    <Dialog v-model:visible="dialogVisible" :header="editingTemplate ? 'Edit Template' : 'New Template'" modal :style="{ width: '700px' }">
      <div class="flex flex-col gap-5 pt-2">
        <!-- Name -->
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Template Name *</label>
          <InputText v-model="form.name" class="w-full" placeholder="e.g. 32-Channel Stage" />
        </div>

        <!-- Format row -->
        <div class="grid grid-cols-2 gap-4">
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium">Channel Count *</label>
            <InputNumber v-model="form.channel_count" :min="1" :max="64" @update:modelValue="syncChannelNames" class="w-full" />
          </div>
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

        <!-- Channel names -->
        <div class="flex flex-col gap-2">
          <div class="flex items-center justify-between">
            <label class="text-sm font-medium">Channel Names</label>
            <Button label="Auto-number" size="small" severity="secondary" text @click="autoNumberChannels" />
          </div>
          <div class="border border-surface-200 dark:border-surface-700 rounded-lg overflow-hidden">
            <div class="max-h-64 overflow-y-auto">
              <table class="w-full text-sm">
                <thead class="sticky top-0 surface-100 dark:bg-surface-800">
                  <tr>
                    <th class="text-left px-3 py-2 w-16 text-surface-500">Ch #</th>
                    <th class="text-left px-3 py-2 text-surface-500">Name</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(_, idx) in form.channel_names" :key="idx" class="border-t border-surface-100 dark:border-surface-700">
                    <td class="px-3 py-1 text-surface-400 font-mono text-xs">{{ idx + 1 }}</td>
                    <td class="px-2 py-1">
                      <InputText v-model="form.channel_names[idx]" size="small" class="w-full" :placeholder="`Ch ${idx + 1}`" />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Metadata defaults -->
        <div class="flex flex-col gap-2">
          <label class="text-sm font-medium">Default Metadata</label>
          <div class="grid grid-cols-2 gap-3">
            <div v-for="field in METADATA_FIELDS" :key="field.key" class="flex flex-col gap-1">
              <label class="text-xs text-surface-400">{{ field.label }}</label>
              <InputText v-model="form.metadata_defaults[field.key]" size="small" class="w-full" :placeholder="field.placeholder" />
            </div>
          </div>
        </div>

        <!-- Filename pattern -->
        <div class="flex flex-col gap-1.5">
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
            Leave blank to use <code class="font-mono">{channel}</code>.
          </p>
          <p v-if="form.filename_pattern.trim()" class="text-xs font-mono text-primary-400">
            Preview: {{ previewFilename(form.filename_pattern) }}
          </p>
        </div>
      </div>

      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="dialogVisible = false" />
        <Button :label="editingTemplate ? 'Save Changes' : 'Create Template'" :loading="saving" @click="submitDialog" />
      </template>
    </Dialog>

    <ConfirmDialog />
    <Toast />
  </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import { api } from '@/api/client'
import AppLayout from '@/components/AppLayout.vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import ProgressSpinner from 'primevue/progressspinner'
import ConfirmDialog from 'primevue/confirmdialog'
import Toast from 'primevue/toast'

interface Template {
  id: number
  name: string
  channel_count: number
  channel_names: string[]
  sample_rate: number
  bit_depth: number
  codec: string
  container: string
  channel_source_defaults: any[]
  metadata_defaults: Record<string, string>
  filename_pattern: string | null
}

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
]

const confirm = useConfirm()
const toast = useToast()
const queryClient = useQueryClient()

const { data: templates, isLoading } = useQuery<Template[]>({
  queryKey: ['templates'],
  queryFn: async () => (await api.get<Template[]>('/api/templates')).data,
})

const dialogVisible = ref(false)
const saving = ref(false)
const editingTemplate = ref<Template | null>(null)

const defaultForm = () => ({
  name: '',
  channel_count: 8,
  channel_names: Array.from({ length: 8 }, (_, i) => `Ch ${i + 1}`),
  sample_rate: 48000,
  bit_depth: 24,
  codec: 'pcm_s24le',
  container: 'wav',
  metadata_defaults: {} as Record<string, string>,
  filename_pattern: '',
})

const form = reactive(defaultForm())

function openCreate() {
  editingTemplate.value = null
  Object.assign(form, defaultForm())
  dialogVisible.value = true
}

function openEdit(tmpl: Template) {
  editingTemplate.value = tmpl
  form.name = tmpl.name
  form.channel_count = tmpl.channel_count
  form.channel_names = [...tmpl.channel_names]
  form.sample_rate = tmpl.sample_rate
  form.bit_depth = tmpl.bit_depth
  form.codec = tmpl.codec
  form.container = tmpl.container
  form.metadata_defaults = { ...tmpl.metadata_defaults }
  form.filename_pattern = tmpl.filename_pattern ?? ''
  dialogVisible.value = true
}

function syncChannelNames(count: number) {
  const names = [...form.channel_names]
  while (names.length < count) names.push(`Ch ${names.length + 1}`)
  form.channel_names = names.slice(0, count)
}

function autoNumberChannels() {
  form.channel_names = Array.from({ length: form.channel_count }, (_, i) => `Ch ${i + 1}`)
}

async function submitDialog() {
  if (!form.name.trim()) return
  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      channel_count: form.channel_count,
      channel_names: form.channel_names,
      sample_rate: form.sample_rate,
      bit_depth: form.bit_depth,
      codec: form.codec,
      container: form.container,
      metadata_defaults: form.metadata_defaults,
      filename_pattern: form.filename_pattern.trim() || null,
    }
    if (editingTemplate.value) {
      await api.put(`/api/templates/${editingTemplate.value.id}`, payload)
      toast.add({ severity: 'success', summary: 'Template updated', life: 3000 })
    } else {
      await api.post('/api/templates', payload)
      toast.add({ severity: 'success', summary: 'Template created', life: 3000 })
    }
    queryClient.invalidateQueries({ queryKey: ['templates'] })
    dialogVisible.value = false
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.response?.data?.detail ?? 'Failed', life: 4000 })
  } finally {
    saving.value = false
  }
}

function previewFilename(pattern: string): string {
  const now = new Date()
  const pad = (n: number, l = 2) => String(n).padStart(l, '0')
  const date = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`
  const time = `${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
  return (pattern || '{channel}')
    .replace(/\{channel\}/g, '001')
    .replace(/\{datetime\}/g, `${date}_${time}`)
    .replace(/\{date\}/g, date)
    .replace(/\{time\}/g, time) + '.wav'
}

function confirmDelete(tmpl: Template) {
  confirm.require({
    message: `Delete template "${tmpl.name}"?`,
    header: 'Delete Template',
    icon: 'pi pi-exclamation-triangle',
    rejectClass: 'p-button-secondary p-button-text',
    accept: async () => {
      try {
        await api.delete(`/api/templates/${tmpl.id}`)
        queryClient.invalidateQueries({ queryKey: ['templates'] })
        toast.add({ severity: 'success', summary: 'Template deleted', life: 3000 })
      } catch (e: any) {
        toast.add({ severity: 'error', summary: 'Error', detail: e.response?.data?.detail ?? 'Failed', life: 4000 })
      }
    },
  })
}
</script>
