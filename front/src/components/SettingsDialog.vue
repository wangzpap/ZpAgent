<!--
  SettingsDialog.vue — 系统设置弹窗（多板块架构）

  侧栏导航 + 内容面板的经典设置页布局：
    - 左侧：板块导航列表（模型配置、对话压缩、未来更多...）
    - 右侧：当前选中板块的配置表单
    - 底部：统一的保存/取消操作栏 + Toast 提示

  扩展方式：新增板块只需创建对应组件并在 navItems 中注册。

  Props:
    visible - 是否显示弹窗

  Events:
    close   - 关闭弹窗
-->
<template>
  <Teleport to="body">
    <Transition name="settings-dialog">
      <div v-if="visible" class="settings-overlay" @click.self="$emit('close')">
        <div class="settings-dialog">
          <!-- 弹窗头部 -->
          <div class="settings-header">
            <div class="settings-header-left">
              <div class="settings-icon-wrap">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="3"/>
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
                </svg>
              </div>
              <div>
                <h2 class="settings-title">系统设置</h2>
                <p class="settings-subtitle">配置保存后立即生效，无需重启服务</p>
              </div>
            </div>
            <button class="settings-close-btn" @click="$emit('close')" title="关闭">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2" stroke-linecap="round">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>

          <!-- 主体：侧栏 + 内容 -->
          <div class="settings-main">
            <!-- 侧栏导航 -->
            <nav class="settings-nav">
              <button
                v-for="item in navItems"
                :key="item.key"
                class="nav-item"
                :class="{ active: activeNav === item.key }"
                @click="activeNav = item.key"
              >
                <span class="nav-icon" v-html="item.icon"></span>
                <span class="nav-label">{{ item.label }}</span>
              </button>
            </nav>

            <!-- 内容面板 -->
            <div class="settings-content">
              <ModelSettings
                v-show="activeNav === 'model'"
                ref="modelSettingsRef"
                :active="activeNav === 'model'"
                @toast="showToast"
                @saving="v => saving = v"
              />
              <CompressionSettings
                v-show="activeNav === 'compression'"
                ref="compressionSettingsRef"
                :active="activeNav === 'compression'"
                @toast="showToast"
                @saving="v => saving = v"
              />
            </div>
          </div>

          <!-- 底部操作栏 -->
          <div class="settings-footer">
            <Transition name="toast">
              <div v-if="toastMessage" class="toast" :class="toastType">
                <svg v-if="toastType === 'success'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="12" y1="8" x2="12" y2="12"/>
                  <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                {{ toastMessage }}
              </div>
            </Transition>
            <div class="settings-actions">
              <button class="settings-cancel-btn" @click="$emit('close')" :disabled="saving">
                取消
              </button>
              <button class="settings-save-btn" @click="handleSave" :disabled="saving">
                <span v-if="saving" class="save-loading">
                  <span class="spinner"></span>
                  保存中...
                </span>
                <span v-else>保存配置</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'
import ModelSettings from './settings/ModelSettings.vue'
import CompressionSettings from './settings/CompressionSettings.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])

// ---- 导航配置 ----
// 新增板块时：1. 创建组件  2. 在此数组注册  3. 在 template 中添加 v-show 渲染
const navItems = [
  {
    key: 'model',
    label: '模型配置',
    icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>',
  },
  {
    key: 'compression',
    label: '对话压缩',
    icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="7.5 4.21 12 6.81 16.5 4.21"/><polyline points="7.5 19.79 7.5 14.6 3 12"/><polyline points="21 12 16.5 14.6 16.5 19.79"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>',
  },
]

// ---- 状态 ----
const activeNav = ref('model')
const saving = ref(false)

// 子组件引用（用于调用 save 方法）
const modelSettingsRef = ref(null)
const compressionSettingsRef = ref(null)

// ---- Toast 提示 ----
const toastMessage = ref('')
const toastType = ref('success')
let toastTimer = null

function showToast(message, type = 'success') {
  toastMessage.value = message
  toastType.value = type
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastMessage.value = ''
  }, 3000)
}

// ---- 弹窗打开/关闭 ----
watch(() => props.visible, (newVal) => {
  if (!newVal) {
    toastMessage.value = ''
    saving.value = false
    return
  }
  // 打开时重置到第一个板块
  activeNav.value = 'model'
})

// ---- 保存当前板块 ----
async function handleSave() {
  let success = false
  if (activeNav.value === 'model' && modelSettingsRef.value) {
    success = await modelSettingsRef.value.save()
  } else if (activeNav.value === 'compression' && compressionSettingsRef.value) {
    success = await compressionSettingsRef.value.save()
  }
  if (success) {
    setTimeout(() => emit('close'), 1500)
  }
}
</script>

<style scoped>
.settings-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  animation: settings-overlay-in 0.2s ease-out;
}

@keyframes settings-overlay-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}

.settings-dialog {
  width: 860px;
  height: 620px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: var(--shadow-float);
  animation: settings-dialog-in 0.3s var(--ease-out);
}

@keyframes settings-dialog-in {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* Vue Transition */
.settings-dialog-enter-active {
  transition: all 0.3s var(--ease-out);
}
.settings-dialog-leave-active {
  transition: all 0.2s ease-in;
}
.settings-dialog-enter-from,
.settings-dialog-leave-to {
  opacity: 0;
}
.settings-dialog-enter-from .settings-dialog,
.settings-dialog-leave-to .settings-dialog {
  transform: translateY(20px) scale(0.96);
}

/* ---- 头部 ---- */
.settings-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--border);
  background: linear-gradient(135deg, rgba(232, 187, 94, 0.04) 0%, transparent 60%);
}

.settings-header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.settings-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--accent-dim);
  color: var(--accent);
  border: 1px solid var(--border-accent);
  flex-shrink: 0;
}

.settings-title {
  font-size: 16px;
  font-weight: 650;
  color: var(--text-primary);
  letter-spacing: 0.2px;
  line-height: 1.3;
}

.settings-subtitle {
  font-size: 12px;
  color: var(--text-primary);
  margin-top: 3px;
  line-height: 1.4;
}

.settings-close-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 6px;
  border-radius: var(--radius-xxs);
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: -2px;
  margin-right: -4px;
}

.settings-close-btn:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

/* ---- 主体（侧栏 + 内容） ---- */
.settings-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* ---- 侧栏导航 ---- */
.settings-nav {
  width: 160px;
  flex-shrink: 0;
  padding: 16px 12px;
  border-right: 1px solid var(--border);
  background: var(--bg-base);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: none;
  border-radius: var(--radius-xs);
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  font-family: var(--font-ui);
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
  width: 100%;
}

.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--accent-dim);
  color: var(--accent);
  font-weight: 600;
  border: 1px solid var(--border-accent);
}

.nav-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  opacity: 0.75;
}

.nav-item.active .nav-icon {
  opacity: 1;
}

.nav-label {
  white-space: nowrap;
}

/* ---- 内容面板 ---- */
.settings-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

/* ---- 底部操作栏 ---- */
.settings-footer {
  padding: 14px 24px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.settings-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.settings-cancel-btn {
  padding: 10px 24px;
  background: transparent;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xs);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
  font-family: var(--font-ui);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.settings-cancel-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.settings-cancel-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.settings-save-btn {
  padding: 10px 28px;
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-hover) 100%);
  color: var(--bg-base);
  border: none;
  border-radius: var(--radius-xs);
  font-size: 13px;
  font-weight: 650;
  font-family: var(--font-ui);
  cursor: pointer;
  transition: all var(--transition-normal);
  box-shadow: 0 2px 10px var(--accent-glow);
  position: relative;
  overflow: hidden;
}

.settings-save-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.22) 0%, transparent 50%);
  opacity: 0;
  transition: opacity var(--transition-normal);
}

.settings-save-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px var(--accent-glow);
}

.settings-save-btn:hover:not(:disabled)::before {
  opacity: 1;
}

.settings-save-btn:active:not(:disabled) {
  transform: translateY(0);
}

.settings-save-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.save-loading {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(0, 0, 0, 0.15);
  border-top-color: var(--bg-base);
  border-radius: 50%;
  animation: spin 0.65s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ---- Toast 提示 ---- */
.toast {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: var(--radius-xs);
  font-size: 12px;
  font-weight: 500;
  line-height: 1.4;
}

.toast.success {
  background: rgba(74, 222, 128, 0.10);
  color: var(--success);
  border: 1px solid rgba(74, 222, 128, 0.20);
}

.toast.error {
  background: rgba(239, 107, 107, 0.10);
  color: var(--danger);
  border: 1px solid rgba(239, 107, 107, 0.20);
}

.toast svg {
  flex-shrink: 0;
}

.toast-enter-active {
  transition: all 0.3s var(--ease-out);
}
.toast-leave-active {
  transition: all 0.2s ease-in;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
