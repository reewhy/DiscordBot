import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    allowedHosts: true, // serve per il tunnel (cloudflared / ngrok)
    proxy: {
      '/api': 'http://localhost:4001',
      '/socket.io': { target: 'http://localhost:4001', ws: true }
    }
  }
})
