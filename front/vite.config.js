import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // 将 /api 请求代理到后端服务
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // 禁用代理层缓冲，确保 SSE 流式响应实时转发
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            // 覆盖缓冲相关头，防止代理层攒数据
            proxyRes.headers['cache-control'] = 'no-cache, no-transform'
            proxyRes.headers['x-accel-buffering'] = 'no'
            delete proxyRes.headers['content-length']
          })
        },
      },
    },
  },
})
