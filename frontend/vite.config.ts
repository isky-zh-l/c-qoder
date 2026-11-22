import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

function normalizeBase(value: string): string {
  const path = value.startsWith('/') ? value : `/${value}`
  return path.endsWith('/') ? path : `${path}/`
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const base = normalizeBase(env.VITE_BASE_PATH || '/c/')
  const proxyTarget = env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    base,
    plugins: [vue()],
    build: {
      outDir: env.VITE_OUT_DIR || 'dist',
      emptyOutDir: true,
    },
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        [`${base}api`]: {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
