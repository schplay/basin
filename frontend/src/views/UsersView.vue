<template>
  <AppLayout>
    <ConfirmDialog />
    <Toast />
    <div class="p-6 max-w-5xl">
      <div class="flex items-center justify-between mb-6">
        <div>
          <h1 class="text-2xl font-semibold">Users</h1>
          <p class="text-sm text-surface-400 mt-0.5">Manage accounts and group access</p>
        </div>
        <Button label="Add User" icon="pi pi-plus" @click="openCreate" />
      </div>

      <DataTable :value="users ?? []" :loading="isPending" stripedRows size="small"
        class="surface-card border border-surface-200 dark:border-surface-700 rounded-xl">
        <Column field="username" header="Username" />
        <Column header="Role" style="width: 110px">
          <template #body="{ data }">
            <Tag :value="data.role" :severity="roleSeverity(data.role)" class="text-xs capitalize" />
          </template>
        </Column>
        <Column header="Status" style="width: 90px">
          <template #body="{ data }">
            <Tag :value="data.is_active ? 'Active' : 'Inactive'"
              :severity="data.is_active ? 'success' : 'secondary'" class="text-xs" />
          </template>
        </Column>
        <Column header="Groups" style="width: 200px">
          <template #body="{ data }">
            <span v-if="data.role === 'admin'" class="text-surface-400 text-xs italic">All groups</span>
            <span v-else class="text-xs text-surface-400">
              {{ data.group_ids?.length ? `${data.group_ids.length} group(s)` : 'No access' }}
            </span>
          </template>
        </Column>
        <Column header="Actions" style="width: 160px">
          <template #body="{ data }">
            <div class="flex gap-1">
              <Button icon="pi pi-pencil" text rounded size="small" @click="openEdit(data)" />
              <Button icon="pi pi-folder-open" text rounded size="small" severity="secondary"
                title="Manage group access" @click="openGroupAccess(data)" />
              <Button icon="pi pi-ban" text rounded size="small" severity="danger"
                title="Deactivate user" @click="confirmDeactivate(data)"
                :disabled="data.id === currentUserId" />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>

    <!-- Create / Edit dialog -->
    <Dialog v-model:visible="dialogVisible" :header="editingId ? 'Edit User' : 'Add User'" modal style="width: 26rem">
      <div class="space-y-4 py-2">
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium">Username</label>
          <InputText v-model="form.username" class="w-full" :disabled="!!editingId" />
        </div>
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium">{{ editingId ? 'New Password' : 'Password' }}
            <span v-if="editingId" class="text-surface-500 font-normal">(leave blank to keep current)</span>
          </label>
          <InputText v-model="form.password" type="password" placeholder="••••••••" class="w-full" />
        </div>
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium">Role</label>
          <Select v-model="form.role" :options="roleOptions" option-label="label" option-value="value" class="w-full" />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="dialogVisible = false" />
        <Button label="Save" :loading="saveMutation.isPending.value" @click="saveMutation.mutate()" />
      </template>
    </Dialog>

    <!-- Group access dialog -->
    <Dialog v-model:visible="groupAccessVisible" :header="`Group Access — ${accessUser?.username}`"
      modal style="width: 28rem">
      <div class="py-2">
        <p class="text-sm text-surface-400 mb-4">Select groups this user can see and record into.</p>
        <div v-if="groupsLoading" class="text-sm text-surface-400">Loading…</div>
        <div v-else class="space-y-2 max-h-80 overflow-y-auto">
          <div v-for="g in flatGroups" :key="g.id" class="flex items-center gap-3 py-1">
            <Checkbox
              :inputId="`grp-${g.id}`"
              :value="g.id"
              v-model="selectedGroupIds"
            />
            <label :for="`grp-${g.id}`" class="text-sm cursor-pointer" :style="{ paddingLeft: `${g.depth * 1}rem` }">
              {{ g.name }}
            </label>
          </div>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="groupAccessVisible = false" />
        <Button label="Save Access" :loading="savingAccess" @click="saveGroupAccess" />
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
import { useAuthStore } from '@/stores/auth'
import AppLayout from '@/components/AppLayout.vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Checkbox from 'primevue/checkbox'
import ConfirmDialog from 'primevue/confirmdialog'
import Toast from 'primevue/toast'

interface UserOut {
  id: number
  username: string
  role: string
  is_active: boolean
  group_ids: number[]
}

const qc = useQueryClient()
const toast = useToast()
const confirm = useConfirm()
const auth = useAuthStore()
const currentUserId = computed(() => auth.user?.id)

const { data: users, isPending } = useQuery<UserOut[]>({
  queryKey: ['users'],
  queryFn: () => api.get('/api/users').then(r => r.data),
})

const { data: groups, isLoading: groupsLoading } = useQuery({
  queryKey: ['groups'],
  queryFn: () => api.get('/api/groups').then(r => r.data),
})

// Flatten the nested group tree for display
function flatten(list: any[], depth = 0): { id: number; name: string; depth: number }[] {
  return list.flatMap(g => [{ id: g.id, name: g.name, depth }, ...flatten(g.children ?? [], depth + 1)])
}
const flatGroups = computed(() => flatten(groups.value ?? []))

const roleOptions = [
  { label: 'Admin', value: 'admin' },
  { label: 'Editor', value: 'editor' },
  { label: 'Operator', value: 'operator' },
]

function roleSeverity(role: string) {
  return role === 'admin' ? 'danger' : role === 'editor' ? 'warn' : 'secondary'
}

// ── Create / Edit ──────────────────────────────────────────────
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const form = ref({ username: '', password: '', role: 'operator' })

function openCreate() {
  editingId.value = null
  form.value = { username: '', password: '', role: 'operator' }
  dialogVisible.value = true
}

function openEdit(u: UserOut) {
  editingId.value = u.id
  form.value = { username: u.username, password: '', role: u.role }
  dialogVisible.value = true
}

const saveMutation = useMutation({
  mutationFn: () => {
    const payload: Record<string, any> = { role: form.value.role }
    if (!editingId.value) {
      payload.username = form.value.username
      payload.password = form.value.password
    } else if (form.value.password) {
      payload.password = form.value.password
    }
    return editingId.value
      ? api.put(`/api/users/${editingId.value}`, payload)
      : api.post('/api/users', payload)
  },
  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ['users'] })
    dialogVisible.value = false
    toast.add({ severity: 'success', summary: editingId.value ? 'User updated' : 'User created', life: 3000 })
  },
  onError: (err: any) => {
    toast.add({ severity: 'error', summary: 'Save failed', detail: err.response?.data?.detail, life: 5000 })
  },
})

function confirmDeactivate(u: UserOut) {
  confirm.require({
    message: `Deactivate user "${u.username}"? They will no longer be able to log in.`,
    header: 'Confirm deactivation',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      await api.delete(`/api/users/${u.id}`)
      qc.invalidateQueries({ queryKey: ['users'] })
      toast.add({ severity: 'success', summary: 'User deactivated', life: 3000 })
    },
  })
}

// ── Group access ──────────────────────────────────────────────
const groupAccessVisible = ref(false)
const accessUser = ref<UserOut | null>(null)
const selectedGroupIds = ref<number[]>([])
const savingAccess = ref(false)

function openGroupAccess(u: UserOut) {
  accessUser.value = u
  selectedGroupIds.value = [...(u.group_ids ?? [])]
  groupAccessVisible.value = true
}

async function saveGroupAccess() {
  if (!accessUser.value) return
  savingAccess.value = true
  try {
    await api.put(`/api/users/${accessUser.value.id}/groups`, { group_ids: selectedGroupIds.value })
    qc.invalidateQueries({ queryKey: ['users'] })
    groupAccessVisible.value = false
    toast.add({ severity: 'success', summary: 'Group access updated', life: 3000 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Save failed', detail: e.response?.data?.detail, life: 5000 })
  } finally {
    savingAccess.value = false
  }
}
</script>
