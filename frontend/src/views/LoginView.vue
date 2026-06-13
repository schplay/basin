<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const toast = useToast()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const loading = ref(false)

async function submit() {
  if (!username.value || !password.value) return
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    router.push('/')
  } catch {
    toast.add({ severity: 'error', summary: 'Login failed', detail: 'Invalid username or password', life: 4000 })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-gray-950 flex items-center justify-center p-4">
    <div class="w-full max-w-sm">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold text-white tracking-tight">Basin</h1>
        <p class="text-gray-400 text-sm mt-1">Multitrack Recording Appliance</p>
      </div>

      <form class="bg-gray-900 rounded-2xl p-8 shadow-xl space-y-5 border border-gray-800" @submit.prevent="submit">
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium text-gray-300">Username</label>
          <InputText
            v-model="username"
            placeholder="admin"
            autocomplete="username"
            class="w-full"
            :disabled="loading"
          />
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium text-gray-300">Password</label>
          <Password
            v-model="password"
            :feedback="false"
            toggle-mask
            placeholder="••••••••"
            autocomplete="current-password"
            input-class="w-full"
            class="w-full"
            :disabled="loading"
          />
        </div>

        <Button
          type="submit"
          label="Sign in"
          class="w-full"
          :loading="loading"
        />
      </form>
    </div>
  </div>
</template>
