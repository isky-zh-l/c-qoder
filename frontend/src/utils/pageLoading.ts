import { reactive } from 'vue'

export const pageLoadingState = reactive({
  active: false,
  label: '',
})

let token = 0
let safetyTimer: number | null = null

function clearSafety() {
  if (safetyTimer !== null) {
    window.clearTimeout(safetyTimer)
    safetyTimer = null
  }
}

export function startPageLoading(label: string): number {
  token += 1
  pageLoadingState.active = true
  pageLoadingState.label = label
  clearSafety()
  const current = token
  safetyTimer = window.setTimeout(() => {
    if (token === current) {
      pageLoadingState.active = false
      pageLoadingState.label = ''
    }
  }, 15000)
  return token
}

export function endPageLoading(value: number): void {
  if (value !== token) return
  clearSafety()
  pageLoadingState.active = false
  pageLoadingState.label = ''
}

export function clearPageLoading(): void {
  token += 1
  clearSafety()
  pageLoadingState.active = false
  pageLoadingState.label = ''
}

export function currentPageLoadingToken(): number {
  return token
}
