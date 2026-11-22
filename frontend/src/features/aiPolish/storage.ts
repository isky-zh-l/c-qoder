export const AI_POLISH_EVENT = 'cq-ai-polish'

export interface AiPolishErrorState {
  message: string
  at: number
}

const errorKey = (userId: number | string) => `cq.aiPolish.error.${userId}`

export function saveAiError(userId: number | string, message: string): void {
  try {
    window.localStorage.setItem(
      errorKey(userId),
      JSON.stringify({ message, at: Date.now() }),
    )
  } catch {
    // Storage is optional; the editor still shows the failure.
  }
}

export function loadAiError(userId: number | string): AiPolishErrorState | null {
  try {
    const raw = window.localStorage.getItem(errorKey(userId))
    if (!raw) return null
    const value = JSON.parse(raw) as AiPolishErrorState
    return typeof value?.message === 'string' ? value : null
  } catch {
    return null
  }
}

export function clearAiError(userId: number | string): void {
  try {
    window.localStorage.removeItem(errorKey(userId))
  } catch {
    // Ignore unavailable storage.
  }
}

export function announceAiChange(): void {
  window.dispatchEvent(new Event(AI_POLISH_EVENT))
}