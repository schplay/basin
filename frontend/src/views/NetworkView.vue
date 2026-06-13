<script setup lang="ts">
import { ref } from 'vue'
import { useQuery, useMutation } from '@tanstack/vue-query'
import { useToast } from 'primevue/usetoast'
import AppLayout from '@/components/AppLayout.vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import { api } from '@/api/client'

interface NetworkInterface {
  name: string
  ip: string | null
  prefix: number | null
  mac: string | null
  is_up: boolean
}

const toast = useToast()

const { data: interfaces, isPending, refetch } = useQuery<NetworkInterface[]>({
  queryKey: ['network-interfaces'],
  queryFn: () => api.get('/api/network/interfaces').then(r => r.data),
  refetchInterval: 15_000,
})

// ── Configure dialog ──────────────────────────────────────────
const dialogVisible = ref(false)
const configuring = ref<NetworkInterface | null>(null)
const form = ref({ address: '', prefix: 24, gateway: '', dns: '' })

function openConfigure(iface: NetworkInterface) {
  configuring.value = iface
  form.value = {
    address: iface.ip ?? '',
    prefix: iface.prefix ?? 24,
    gateway: '',
    dns: '8.8.8.8,8.8.4.4',
  }
  dialogVisible.value = true
}

const applyMutation = useMutation({
  mutationFn: () => {
    if (!configuring.value) return Promise.reject()
    const dns = form.value.dns
      ? form.value.dns.split(',').map(s => s.trim()).filter(Boolean)
      : []
    return api.put(`/api/network/interfaces/${configuring.value.name}`, {
      address: form.value.address,
      prefix: form.value.prefix,
      gateway: form.value.gateway || null,
      dns,
    })
  },
  onSuccess: () => {
    dialogVisible.value = false
    toast.add({ severity: 'success', summary: 'Network config applied', detail: 'Changes take effect immediately', life: 4000 })
    setTimeout(() => refetch(), 2000)
  },
  onError: (err: any) => {
    toast.add({ severity: 'error', summary: 'Apply failed', detail: err.response?.data?.detail ?? 'Unknown error', life: 6000 })
  },
})
</script>

<template>
  <AppLayout>
    <div class="p-6">
      <div class="mb-6">
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">Network</h1>
        <p class="text-gray-500 text-sm mt-0.5">View and configure network interfaces</p>
      </div>

      <div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl overflow-hidden">
        <DataTable :value="interfaces ?? []" :loading="isPending" class="text-sm">
          <Column header="Interface" field="name">
            <template #body="{ data }">
              <span class="font-mono font-medium">{{ data.name }}</span>
            </template>
          </Column>
          <Column header="Status">
            <template #body="{ data }">
              <Tag :value="data.is_up ? 'Up' : 'Down'" :severity="data.is_up ? 'success' : 'secondary'" />
            </template>
          </Column>
          <Column header="IP address">
            <template #body="{ data }">
              <span v-if="data.ip" class="font-mono">{{ data.ip }}/{{ data.prefix }}</span>
              <span v-else class="text-gray-400">—</span>
            </template>
          </Column>
          <Column header="MAC address">
            <template #body="{ data }">
              <span class="font-mono text-gray-500">{{ data.mac ?? '—' }}</span>
            </template>
          </Column>
          <Column header="Actions" style="width: 9rem">
            <template #body="{ data }">
              <Button
                label="Configure"
                size="small"
                severity="secondary"
                @click="openConfigure(data)"
              />
            </template>
          </Column>
        </DataTable>
      </div>

      <p class="text-xs text-gray-400 mt-3">
        Changes are written via netplan and applied immediately. The appliance may become temporarily unreachable if the IP address changes — reconnect using the new address shown on the kiosk display.
      </p>
    </div>

    <!-- Configure dialog -->
    <Dialog
      v-model:visible="dialogVisible"
      :header="`Configure ${configuring?.name}`"
      modal
      style="width: 28rem"
    >
      <div class="space-y-4 py-2">
        <div class="grid grid-cols-3 gap-3">
          <div class="col-span-2 flex flex-col gap-1.5">
            <label class="text-sm font-medium">IP address</label>
            <InputText v-model="form.address" placeholder="192.168.1.100" class="w-full font-mono" />
          </div>
          <div class="flex flex-col gap-1.5">
            <label class="text-sm font-medium">Prefix</label>
            <InputNumber v-model="form.prefix" :min="1" :max="32" class="w-full" />
          </div>
        </div>
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium">Default gateway</label>
          <InputText v-model="form.gateway" placeholder="192.168.1.1" class="w-full font-mono" />
        </div>
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium">DNS servers</label>
          <InputText v-model="form.dns" placeholder="8.8.8.8,8.8.4.4" class="w-full font-mono" />
          <p class="text-xs text-gray-500">Comma-separated</p>
        </div>

        <div class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg p-3 text-sm text-amber-800 dark:text-amber-300">
          <i class="pi pi-exclamation-triangle mr-1"></i>
          Changes apply immediately. If you change the IP, reconnect using the new address.
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="dialogVisible = false" />
        <Button label="Apply" :loading="applyMutation.isPending.value" @click="applyMutation.mutate()" />
      </template>
    </Dialog>
  </AppLayout>
</template>
