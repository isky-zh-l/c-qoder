const SCROLL_KEY = 'c-notes:scroll-positions'
const HOME_RETURN_KEY = 'c-notes:home-return'

function readPositions(): Record<string, number> {
  try {
    const raw = sessionStorage.getItem(SCROLL_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return {}
    }
    const output: Record<string, number> = {}
    for (const [key, value] of Object.entries(parsed)) {
      if (typeof value === 'number' && Number.isFinite(value)) {
        output[key] = value
      }
    }
    return output
  } catch {
    return {}
  }
}

function writePositions(value: Record<string, number>) {
  try {
    sessionStorage.setItem(SCROLL_KEY, JSON.stringify(value))
  } catch {
    // 隐私模式禁用存储时忽略滚动记忆
  }
}

export function saveScrollPosition(path: string) {
  if (!path) return
  const positions = readPositions()
  positions[path] = window.scrollY
  writePositions(positions)
}

export function restoreScrollPosition(path: string): boolean {
  const position = readPositions()[path]
  if (typeof position !== 'number' || !Number.isFinite(position)) {
    return false
  }
  const apply = () => window.scrollTo({ top: position, behavior: 'auto' })
  requestAnimationFrame(() => {
    apply()
    window.setTimeout(apply, 60)
  })
  return true
}

export function rememberHomeReturn(path: string) {
  if (!path) return
  try {
    sessionStorage.setItem(HOME_RETURN_KEY, path)
  } catch {
    // ignore
  }
}

export function consumeHomeReturn(): string | null {
  try {
    const path = sessionStorage.getItem(HOME_RETURN_KEY)
    sessionStorage.removeItem(HOME_RETURN_KEY)
    return path && path.startsWith('/') ? path : null
  } catch {
    return null
  }
}
