/**
 * ZpAgent 前端入口
 *
 * 创建 Vue 应用实例并挂载到 #app 节点。
 * 全局样式在 style.css 中定义（"Warm Slate Pro" 暗色主题）。
 */

import { createApp } from 'vue'
import App from './App.vue'
import './style.css'

createApp(App).mount('#app')
