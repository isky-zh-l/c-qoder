import { reactive } from 'vue'

export const progressState = reactive({
  active: false,
  value: 0,
})

let pending = 0
let creepTimer: number | null = null
let hideTimer: number | null = null

function clearCreep() {
  if (creepTimer !== null) {
    window.clearInterval(creepTimer)
    creepTimer = null
  }
}

function clearHide() {
  if (hideTimer !== null) {
    window.clearTimeout(hideTimer)
    hideTimer = null
  }
}

function creep() {
  clearCreep()
  creepTimer = window.setInterval(() => {
    if (progressState.value < 88) {
      progressState.value = Math.min(
        88,
        progressState.value + Math.max(1, (90 - progressState.value) * 0.06),
      )
    }
  }, 260)
}

export function beginProgress(): void {
  pending += 1
  if (pending > 1) return
  clearHide()
  progressState.active = true
  progressState.value = 8
  creep()
}

export function endProgress(): void {
  pending = Math.max(0, pending - 1)
  if (pending > 0) return
  clearCreep()
  progressState.value = 100
  clearHide()
  hideTimer = window.setTimeout(() => {
    progressState.active = false
    progressState.value = 0
    hideTimer = null
  }, 220)
}
