<template>
  <AppLayout>
  <div class="p-6 max-w-4xl">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-semibold">Recording Groups</h1>
      <Button label="New Group" icon="pi pi-plus" @click="openCreate(null)" />
    </div>

    <div v-if="isLoading" class="flex justify-center py-12">
      <ProgressSpinner />
    </div>

    <div v-else-if="!tree.length" class="text-center py-16 text-surface-400">
      <i class="pi pi-folder-open text-5xl mb-4 block" />
      <p class="text-lg mb-2">No groups yet</p>
      <p class="text-sm mb-6">Create groups to organise your recordings into directories</p>
      <Button label="Create First Group" icon="pi pi-plus" @click="openCreate(null)" />
    </div>

    <div v-else class="surface-card border border-surface-200 dark:border-surface-700 rounded-xl overflow-hidden">
      <Tree
        :value="treeNodes"
        :expandedKeys="expandedKeys"
        class="w-full border-none"
        @update:expandedKeys="expandedKeys = $event"
      >
        <template #default="{ node }">
          <div class="flex items-center justify-between w-full py-1 pr-2">
            <div class="flex items-center gap-2">
              <i class="pi pi-folder text-yellow-500" />
              <span>{{ node.label }}</span>
              <span class="text-xs text-surface-400 font-mono">{{ node.data.filesystem_path }}</span>
            </div>
            <div class="flex items-center gap-1">
              <Button
                icon="pi pi-plus"
                size="small"
                severity="secondary"
                text
                v-tooltip.top="'Add subgroup'"
                @click.stop="openCreate(node.data.id)"
              />
              <Button
                icon="pi pi-pencil"
                size="small"
                severity="secondary"
                text
                v-tooltip.top="'Rename'"
                @click.stop="openRename(node.data)"
              />
              <Button
                icon="pi pi-trash"
                size="small"
                severity="danger"
                text
                v-tooltip.top="'Delete'"
                @click.stop="confirmDelete(node.data)"
              />
            </div>
          </div>
        </template>
      </Tree>
    </div>

    <!-- Create / Rename dialog -->
    <Dialog v-model:visible="dialogVisible" :header="dialogMode === 'create' ? 'New Group' : 'Rename Group'" modal :style="{ width: '420px' }">
      <div class="flex flex-col gap-4 pt-2">
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Name</label>
          <InputText v-model="formName" autofocus @keydown.enter="submitDialog" placeholder="e.g. Live Events" class="w-full" />
        </div>
        <div v-if="dialogMode === 'create' && parentId !== null" class="text-sm text-surface-400">
          Will be created inside: <span class="font-mono font-medium text-surface-300">{{ parentPath }}</span>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="dialogVisible = false" />
        <Button :label="dialogMode === 'create' ? 'Create' : 'Save'" :loading="saving" @click="submitDialog" />
      </template>
    </Dialog>

    <ConfirmDialog />
    <Toast />
  </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import { api } from '@/api/client'
import AppLayout from '@/components/AppLayout.vue'
import Tree from 'primevue/tree'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import ProgressSpinner from 'primevue/progressspinner'
import ConfirmDialog from 'primevue/confirmdialog'
import Toast from 'primevue/toast'

interface Group {
  id: number
  name: string
  parent_id: number | null
  filesystem_path: string
  default_template_id: number | null
  children: Group[]
}

interface TreeNode {
  key: string
  label: string
  data: Group
  children: TreeNode[]
  leaf: boolean
}

const confirm = useConfirm()
const toast = useToast()
const queryClient = useQueryClient()

const { data: tree, isLoading } = useQuery<Group[]>({
  queryKey: ['groups'],
  queryFn: async () => (await api.get<Group[]>('/api/groups')).data,
  initialData: [],
})

function toTreeNodes(groups: Group[]): TreeNode[] {
  return groups.map(g => ({
    key: String(g.id),
    label: g.name,
    data: g,
    children: toTreeNodes(g.children),
    leaf: g.children.length === 0,
  }))
}

const treeNodes = computed(() => toTreeNodes(tree.value ?? []))
const expandedKeys = ref<Record<string, boolean>>({})

// Dialog state
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'rename'>('create')
const formName = ref('')
const saving = ref(false)
const parentId = ref<number | null>(null)
const editingGroup = ref<Group | null>(null)

const parentPath = computed(() => {
  if (parentId.value === null) return null
  function find(groups: Group[]): Group | null {
    for (const g of groups) {
      if (g.id === parentId.value) return g
      const found = find(g.children)
      if (found) return found
    }
    return null
  }
  return find(tree.value ?? [])?.filesystem_path ?? null
})

function openCreate(pid: number | null) {
  dialogMode.value = 'create'
  parentId.value = pid
  formName.value = ''
  dialogVisible.value = true
}

function openRename(group: Group) {
  dialogMode.value = 'rename'
  editingGroup.value = group
  formName.value = group.name
  dialogVisible.value = true
}

async function submitDialog() {
  if (!formName.value.trim()) return
  saving.value = true
  try {
    if (dialogMode.value === 'create') {
      await api.post('/api/groups', { name: formName.value.trim(), parent_id: parentId.value })
      toast.add({ severity: 'success', summary: 'Group created', life: 3000 })
    } else if (editingGroup.value) {
      await api.put(`/api/groups/${editingGroup.value.id}`, { name: formName.value.trim() })
      toast.add({ severity: 'success', summary: 'Group renamed', life: 3000 })
    }
    queryClient.invalidateQueries({ queryKey: ['groups'] })
    dialogVisible.value = false
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.response?.data?.detail ?? 'Failed', life: 4000 })
  } finally {
    saving.value = false
  }
}

function confirmDelete(group: Group) {
  confirm.require({
    message: `Delete group "${group.name}"? This cannot be undone.`,
    header: 'Delete Group',
    icon: 'pi pi-exclamation-triangle',
    rejectClass: 'p-button-secondary p-button-text',
    accept: async () => {
      try {
        await api.delete(`/api/groups/${group.id}`)
        queryClient.invalidateQueries({ queryKey: ['groups'] })
        toast.add({ severity: 'success', summary: 'Group deleted', life: 3000 })
      } catch (e: any) {
        toast.add({ severity: 'error', summary: 'Cannot delete', detail: e.response?.data?.detail ?? 'Failed', life: 4000 })
      }
    },
  })
}
</script>
