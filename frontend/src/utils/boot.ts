interface BootShell {
  set?: (text: string, percent: number) => void
}

export function bootStage(text: string, percent: number): void {
  const boot = (window as Window & { __cqBoot?: BootShell }).__cqBoot
  boot?.set?.(text, percent)
}
