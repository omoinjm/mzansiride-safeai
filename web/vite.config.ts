import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// `npm run dev` proxies /api to the deployed stack: VITE_API_PROXY=https://xxxx.cloudfront.net npm run dev
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react(), tailwindcss()],
    server: env.VITE_API_PROXY
      ? { proxy: { '/api': { target: env.VITE_API_PROXY, changeOrigin: true } } }
      : undefined,
    build: { chunkSizeWarningLimit: 900 },
  }
})
