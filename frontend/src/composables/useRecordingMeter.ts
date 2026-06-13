import { ref, onUnmounted, type Ref } from 'vue'

export interface ChannelMeter {
  channel: number
  rms_db: number
  peak_db: number
}

export interface MeterState {
  connected: boolean
  duration: number
  channels: ChannelMeter[]
}

/**
 * Connects to the recording meter WebSocket and streams level data.
 * Automatically reconnects when the recording is active.
 */
export function useRecordingMeter(recordingId: Ref<number | string>) {
  const state = ref<MeterState>({
    connected: false,
    duration: 0,
    channels: [],
  })

  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let active = true

  function connect() {
    if (!active) return
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/ws/recordings/${recordingId.value}/meters`

    ws = new WebSocket(url)

    ws.onopen = () => {
      state.value.connected = true
    }

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string)
        if (msg.type === 'meters') {
          state.value.duration = msg.duration
          state.value.channels = msg.channels
        }
      } catch {
        // ignore malformed frames
      }
    }

    ws.onclose = () => {
      state.value.connected = false
      // Reconnect after 500 ms while still mounted
      if (active) {
        reconnectTimer = setTimeout(connect, 500)
      }
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  function disconnect() {
    active = false
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    ws?.close()
    ws = null
  }

  connect()

  onUnmounted(disconnect)

  return { state, disconnect, connect }
}

/** Convert a dB value (-90 to 0) to a 0-100 percentage for bar display. */
export function dbToPercent(db: number): number {
  const clamped = Math.max(-90, Math.min(0, db))
  return ((clamped + 90) / 90) * 100
}

/** Colour class for a dB level (green → yellow → red). */
export function dbToColour(db: number): string {
  if (db >= -6) return '#ef4444'   // red
  if (db >= -18) return '#eab308'  // yellow
  return '#22c55e'                  // green
}
