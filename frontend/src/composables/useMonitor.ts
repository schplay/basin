import { ref, onUnmounted } from 'vue'
import { api } from '@/api/client'

/**
 * WebRTC monitor composable — opens a browser audio connection to an AES67 source.
 * Call `start(sourceId)` to begin, `stop()` to end.
 */
export function useMonitor() {
  const isMonitoring = ref(false)
  const error = ref<string | null>(null)

  let pc: RTCPeerConnection | null = null
  let audioEl: HTMLAudioElement | null = null

  async function start(sourceId: number): Promise<void> {
    if (pc) await stop()
    error.value = null

    try {
      pc = new RTCPeerConnection({ iceServers: [] })

      // We only want to receive audio, not send
      pc.addTransceiver('audio', { direction: 'recvonly' })

      pc.ontrack = (event) => {
        audioEl = new Audio()
        audioEl.autoplay = true
        audioEl.srcObject = event.streams[0] ?? null
        audioEl.play().catch(() => {
          // Autoplay may be blocked; user interaction required
          error.value = 'Autoplay blocked — click the page first'
        })
      }

      pc.onconnectionstatechange = () => {
        if (pc && (pc.connectionState === 'failed' || pc.connectionState === 'closed')) {
          isMonitoring.value = false
        }
      }

      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)

      const resp = await api.post<{ sdp: string; type: string }>(
        `/api/sources/${sourceId}/monitor/offer`,
        { sdp: pc.localDescription!.sdp, type: pc.localDescription!.type },
      )

      await pc.setRemoteDescription(new RTCSessionDescription(resp.data))
      isMonitoring.value = true
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? e?.message ?? 'Failed to open monitor'
      await stop()
    }
  }

  async function stop(): Promise<void> {
    if (audioEl) {
      audioEl.pause()
      audioEl.srcObject = null
      audioEl = null
    }
    if (pc) {
      pc.close()
      pc = null
    }
    isMonitoring.value = false
  }

  onUnmounted(stop)

  return { isMonitoring, error, start, stop }
}
