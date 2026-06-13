<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Stepper from 'primevue/stepper'
import StepList from 'primevue/steplist'
import Step from 'primevue/step'
import StepPanels from 'primevue/steppanels'
import StepPanel from 'primevue/steppanel'
import { api } from '@/api/client'

const router = useRouter()
const toast = useToast()

const step = ref(1)
const loading = ref(false)

const adminPassword = ref('')
const adminPasswordConfirm = ref('')
const hostname = ref('basin')
const storagePath = ref('/mnt/basin-storage')

const passwordMismatch = ref(false)

function validateStep1() {
  if (adminPassword.value.length < 8) {
    toast.add({ severity: 'warn', summary: 'Password too short', detail: 'Minimum 8 characters', life: 3000 })
    return false
  }
  if (adminPassword.value !== adminPasswordConfirm.value) {
    passwordMismatch.value = true
    return false
  }
  passwordMismatch.value = false
  return true
}

async function finish() {
  if (!validateStep1()) return
  loading.value = true
  try {
    await api.post('/api/setup/init', {
      admin_password: adminPassword.value,
      hostname: hostname.value,
      storage_path: storagePath.value,
    })
    toast.add({ severity: 'success', summary: 'Setup complete', detail: 'Welcome to Basin', life: 3000 })
    setTimeout(() => router.push('/login'), 1500)
  } catch (err: any) {
    toast.add({ severity: 'error', summary: 'Setup failed', detail: err.response?.data?.detail ?? 'Unknown error', life: 5000 })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-gray-950 flex items-center justify-center p-4">
    <div class="w-full max-w-lg">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold text-white tracking-tight">Basin</h1>
        <p class="text-gray-400 text-sm mt-1">Initial Setup</p>
      </div>

      <div class="bg-gray-900 rounded-2xl p-8 shadow-xl border border-gray-800">
        <Stepper v-model:value="step" linear>
          <StepList>
            <Step :value="1">Admin Account</Step>
            <Step :value="2">System</Step>
            <Step :value="3">Storage</Step>
          </StepList>

          <StepPanels>
            <StepPanel :value="1">
              <div class="py-4 space-y-4">
                <p class="text-gray-400 text-sm">Create the administrator account for Basin.</p>

                <div class="flex flex-col gap-1.5">
                  <label class="text-sm font-medium text-gray-300">Password</label>
                  <Password v-model="adminPassword" :feedback="true" toggle-mask placeholder="Min. 8 characters" input-class="w-full" class="w-full" />
                </div>

                <div class="flex flex-col gap-1.5">
                  <label class="text-sm font-medium text-gray-300">Confirm password</label>
                  <Password v-model="adminPasswordConfirm" :feedback="false" toggle-mask placeholder="Repeat password" input-class="w-full" class="w-full" />
                  <p v-if="passwordMismatch" class="text-red-400 text-xs">Passwords do not match</p>
                </div>
              </div>
              <div class="flex justify-end">
                <Button label="Next" icon="pi pi-arrow-right" icon-pos="right" @click="validateStep1() && (step = 2)" />
              </div>
            </StepPanel>

            <StepPanel :value="2">
              <div class="py-4 space-y-4">
                <p class="text-gray-400 text-sm">Set the hostname for this appliance.</p>
                <div class="flex flex-col gap-1.5">
                  <label class="text-sm font-medium text-gray-300">Hostname</label>
                  <InputText v-model="hostname" placeholder="basin" class="w-full" />
                </div>
              </div>
              <div class="flex justify-between">
                <Button label="Back" severity="secondary" icon="pi pi-arrow-left" @click="step = 1" />
                <Button label="Next" icon="pi pi-arrow-right" icon-pos="right" @click="step = 3" />
              </div>
            </StepPanel>

            <StepPanel :value="3">
              <div class="py-4 space-y-4">
                <p class="text-gray-400 text-sm">Where should recordings be stored by default?</p>
                <div class="flex flex-col gap-1.5">
                  <label class="text-sm font-medium text-gray-300">Storage path</label>
                  <InputText v-model="storagePath" placeholder="/mnt/basin-storage" class="w-full" />
                  <p class="text-gray-500 text-xs">Must be writable by the basin service user. Additional destinations can be configured later.</p>
                </div>
              </div>
              <div class="flex justify-between">
                <Button label="Back" severity="secondary" icon="pi pi-arrow-left" @click="step = 2" />
                <Button label="Finish setup" icon="pi pi-check" icon-pos="right" :loading="loading" @click="finish" />
              </div>
            </StepPanel>
          </StepPanels>
        </Stepper>
      </div>
    </div>
  </div>
</template>
