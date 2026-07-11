<!--
  SettingsDialog.vue — 系统设置弹窗

  模态弹窗形式的配置面板，当前支持 LLM 大模型配置：
    - API 基础地址（默认 DeepSeek）
    - API 密钥（密码输入，支持显示/隐藏切换）
    - 模型名称

  设计为可扩展结构，后续可在同一弹窗中添加更多配置分区。

  Props:
    visible - 是否显示弹窗

  Events:
    close   - 关闭弹窗（点击遮罩层、取消按钮或保存成功后）
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
                <p class="settings-subtitle">配置大模型参数，保存后立即生效</p>
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

          <!-- 配置内容 -->
          <div class="settings-body">
            <!-- LLM 配置分区 -->
            <div class="settings-section">
              <div class="section-label">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                  <path d="M2 17l10 5 10-5"/>
                  <path d="M2 12l10 5 10-5"/>
                </svg>
                大模型配置
              </div>

              <!-- API 地址 -->
              <div class="form-group">
                <label class="form-label">API 地址</label>
                <input
                  v-model="form.base_url"
                  class="form-input"
                  type="text"
                  placeholder="https://api.deepseek.com"
                  spellcheck="false"
                />
                <span class="form-hint">兼容 OpenAI 格式的 API 服务地址</span>
              </div>

              <!-- API 密钥 -->
              <div class="form-group">
                <label class="form-label">
                  API 密钥
                  <span v-if="hasApiKey" class="key-badge">已配置</span>
                  <span v-else class="key-badge empty">未配置</span>
                </label>
                <div class="input-with-toggle">
                  <input
                    v-model="form.api_key"
                    class="form-input"
                    :type="showApiKey ? 'text' : 'password'"
                    :placeholder="hasApiKey ? '留空保持现有密钥不变' : '请输入 API 密钥'"
                    spellcheck="false"
                    autocomplete="off"
                  />
                  <button class="toggle-visibility-btn" @click="showApiKey = !showApiKey" :title="showApiKey ? '隐藏' : '显示'">
                    <!-- 眼睛图标（显示） -->
                    <svg v-if="!showApiKey" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                         stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                      <circle cx="12" cy="12" r="3"/>
                    </svg>
                    <!-- 眼睛+斜线图标（隐藏） -->
                    <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                         stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                      <line x1="1" y1="1" x2="23" y2="23"/>
                    </svg>
                  </button>
                </div>
                <span class="form-hint">DeepSeek、智谱、Moonshot 等服务商的 API Key</span>
              </div>

              <!-- 模型名称 -->
              <div class="form-group">
                <label class="form-label">模型名称</label>
                <input
                  v-model="form.model_name"
                  class="form-input"
                  type="text"
                  placeholder="deepseek-v4-flash"
                  spellcheck="false"
                />
                <span class="form-hint">所使用的大模型标识（如 deepseek-v4-flash、gpt-4o）</span>
              </div>
            </div>
          </div>

          <!-- 底部操作栏 -->
          <div class="settings-footer">
            <!-- 提示信息 -->
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
import { ref, reactive, watch } from 'vue'
import { fetchLlmConfig, saveLlmConfig } from '../api/index.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])

// ---- 表单状态 ----
const form = reactive({
  base_url: 'https://api.deepseek.com',
  api_key: '',
  model_name: 'deepseek-v4-flash',
})
const hasApiKey = ref(false)    // 后端是否已配置 API 密钥
const showApiKey = ref(false)  // 是否显示明文密钥
const saving = ref(false)      // 保存中状态

// ---- Toast 提示 ----
const toastMessage = ref('')
const toastType = ref('success') // 'success' | 'error'
let toastTimer = null

/** 显示 Toast 提示 */
function showToast(message, type = 'success') {
  toastMessage.value = message
  toastType.value = type
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastMessage.value = ''
  }, 3000)
}

// ---- 弹窗打开时加载配置 ----
watch(() => props.visible, async (newVal) => {
  if (!newVal) {
    // 关闭时重置状态
    showApiKey.value = false
    toastMessage.value = ''
    return
  }

  // 打开时从后端加载当前配置
  try {
    const config = await fetchLlmConfig()
    form.base_url = config.base_url
    form.model_name = config.model_name
    form.api_key = ''  // 始终清空，让用户主动输入
    hasApiKey.value = config.has_api_key
  } catch (e) {
    showToast(e.message, 'error')
  }
})

// ---- 保存配置 ----
async function handleSave() {
  saving.value = true
  try {
    const msg = await saveLlmConfig({
      base_url: form.base_url.trim(),
      api_key: form.api_key.trim(),
      model_name: form.model_name.trim(),
    })
    showToast(msg || '配置已保存并立即生效', 'success')
    // 保存成功后延迟关闭弹窗
    setTimeout(() => emit('close'), 1500)
  } catch (e) {
    showToast(e.message, 'error')
  } finally {
    saving.value = false
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
  width: 480px;
  max-width: 92vw;
  max-height: 85vh;
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
  padding: 24px 24px 20px;
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
  color: var(--text-muted);
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

/* ---- 内容区 ---- */
.settings-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.settings-section {
  margin-bottom: 8px;
}

.section-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  letter-spacing: 0.5px;
  text-transform: uppercase;
  margin-bottom: 18px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

.section-label svg {
  opacity: 0.7;
}

/* ---- 表单组 ---- */
.form-group {
  margin-bottom: 20px;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 550;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.key-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-xxs);
  letter-spacing: 0.3px;
  background: rgba(74, 222, 128, 0.10);
  color: var(--success);
  border: 1px solid rgba(74, 222, 128, 0.20);
}

.key-badge.empty {
  background: rgba(239, 107, 107, 0.10);
  color: var(--danger);
  border-color: rgba(239, 107, 107, 0.20);
}

.form-input {
  width: 100%;
  padding: 10px 14px;
  background: var(--bg-input);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xs);
  color: var(--text-primary);
  font-size: 13px;
  font-family: var(--font-mono);
  line-height: 1.5;
  outline: none;
  transition: all var(--transition-fast);
}

.form-input:focus {
  border-color: var(--border-accent);
  box-shadow: 0 0 0 3px var(--accent-dim);
}

.form-input::placeholder {
  color: var(--text-muted);
  opacity: 0.5;
  font-family: var(--font-mono);
}

.form-hint {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 6px;
  opacity: 0.6;
  line-height: 1.4;
}

/* ---- 密钥输入框（带显示/隐藏切换） ---- */
.input-with-toggle {
  position: relative;
  display: flex;
  align-items: center;
}

.input-with-toggle .form-input {
  padding-right: 42px;
}

.toggle-visibility-btn {
  position: absolute;
  right: 8px;
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px 6px;
  border-radius: var(--radius-xxs);
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
}

.toggle-visibility-btn:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

/* ---- 底部操作栏 ---- */
.settings-footer {
  padding: 16px 24px;
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
  box-shadow: 0 2px 10px var(--accent-glow), var(--shadow-inset);
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
  box-shadow: 0 6px 20px var(--accent-glow), var(--shadow-inset);
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

/* Toast 过渡动画 */
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
