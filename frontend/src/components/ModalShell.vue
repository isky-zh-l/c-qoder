<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    eyebrow?: string
    dismissible?: boolean
    size?: 'small' | 'medium' | 'large'
  }>(),
  {
    eyebrow: '',
    dismissible: true,
    size: 'medium',
  },
)

const emit = defineEmits<{
  close: []
}>()

const panel = ref<HTMLElement | null>(null)

function requestClose() {
  if (props.dismissible) {
    emit('close')
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    requestClose()
    return
  }
  if (event.key !== 'Tab' || !panel.value) {
    return
  }
  const focusable = Array.from(
    panel.value.querySelectorAll<HTMLElement>(
      'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((element) => element.offsetParent !== null)
  if (!focusable.length) {
    return
  }
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

watch(
  () => props.open,
  async (open) => {
    document.body.classList.toggle('modal-open', open)
    if (!open) {
      window.removeEventListener('keydown', onKeydown)
      return
    }
    window.addEventListener('keydown', onKeydown)
    await nextTick()
    const firstInput =
      panel.value?.querySelector<HTMLElement>(
        'input[type="text"]:not([disabled]), select:not([disabled]), textarea:not([disabled])',
      ) ??
      panel.value?.querySelector<HTMLElement>('button:not([disabled])')
    firstInput?.focus()
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.classList.remove('modal-open')
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="modal-root">
        <div class="modal-backdrop" @click="requestClose"></div>
        <section
          ref="panel"
          class="modal-panel"
          :class="`size-${size}`"
          role="dialog"
          aria-modal="true"
          :aria-label="title"
        >
          <header class="modal-head">
            <div>
              <p v-if="eyebrow" class="modal-eyebrow">{{ eyebrow }}</p>
              <h2>{{ title }}</h2>
            </div>
            <button
              type="button"
              class="modal-close"
              aria-label="关闭"
              @click="requestClose"
            >
              <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path
                  d="m5 5 10 10M15 5 5 15"
                  stroke="currentColor"
                  stroke-width="1.5"
                  stroke-linecap="round"
                />
              </svg>
            </button>
          </header>
          <div class="modal-body">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="modal-foot">
            <slot name="footer" />
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-root {
  position: fixed;
  inset: 0;
  z-index: 160;
  display: grid;
  place-items: center;
  padding: 22px;
}

.modal-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(33, 27, 51, 0.42);
}

.modal-panel {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  width: min(520px, 100%);
  max-height: min(86vh, 760px);
  overflow: hidden;
  border: 1px solid rgba(231, 225, 247, 0.96);
  border-radius: 22px;
  background:
    radial-gradient(240px 140px at 100% 0%, rgba(115, 87, 255, 0.08), transparent 70%),
    #fff;
  box-shadow: 0 34px 90px -30px rgba(33, 27, 51, 0.55);
}

.modal-panel.size-small {
  width: min(420px, 100%);
}

.modal-panel.size-large {
  width: min(720px, 100%);
}

.modal-head {
  display: flex;
  gap: 20px;
  align-items: flex-start;
  justify-content: space-between;
  padding: 22px 24px 16px;
  border-bottom: 1px solid var(--border);
}

.modal-eyebrow {
  margin-bottom: 5px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 8.5px;
  font-weight: 650;
  letter-spacing: 0.17em;
}

.modal-head h2 {
  font-size: 20px;
  letter-spacing: -0.02em;
}

.modal-close {
  display: grid;
  flex: none;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--muted-strong);
  background: #fff;
  cursor: pointer;
}

.modal-close svg {
  width: 15px;
  height: 15px;
}

.modal-body {
  padding: 20px 24px;
  overflow-y: auto;
}

.modal-foot {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  padding: 15px 24px 20px;
  border-top: 1px solid var(--border);
  background: rgba(251, 249, 255, 0.7);
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-active .modal-panel,
.modal-leave-active .modal-panel {
  transition:
    transform 0.24s cubic-bezier(0.2, 0.8, 0.2, 1),
    opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-panel,
.modal-leave-to .modal-panel {
  opacity: 0;
  transform: translateY(12px) scale(0.98);
}

@media (max-width: 560px) {
  .modal-root {
    align-items: end;
    padding: 0;
  }

  .modal-panel,
  .modal-panel.size-small,
  .modal-panel.size-large {
    width: 100%;
    max-height: 88vh;
    border-radius: 22px 22px 0 0;
  }

  .modal-head {
    padding: 20px 18px 14px;
  }

  .modal-body {
    padding: 18px;
  }

  .modal-foot {
    padding: 14px 18px calc(18px + env(safe-area-inset-bottom));
  }
}
</style>
