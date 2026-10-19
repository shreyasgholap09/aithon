import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ['@mediapipe/tasks-vision']
  },
  server: {
    host: '0.0.0.0', // Bind to 0.0.0.0 so port forwarding & external devices work!
    port: 5173,
    strictPort: false
  }
})
