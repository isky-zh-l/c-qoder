import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './styles/main.css'
import './styles/auth.css'
import './styles/code.css'

function waitForMainCss(): Promise<void> {
  const link = document.querySelector<HTMLLinkElement>('link[data-cq-main]')
  if (!link || link.sheet) {
    return Promise.resolve()
  }
  return new Promise((resolve) => {
    let settled = false
    const done = () => {
      if (settled) return
      settled = true
      resolve()
    }
    link.addEventListener('load', done, { once: true })
    link.addEventListener('error', done, { once: true })
    window.setTimeout(done, 5000)
  })
}

async function boot() {
  await waitForMainCss()
  createApp(App).use(router).mount('#app')
}

void boot()
