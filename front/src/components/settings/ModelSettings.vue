<!--
  ModelSettings.vue — 大模型配置板块

  从原 SettingsDialog 中拆出的 LLM 配置表单：
    - API 基础地址
    - API 密钥（密码输入，支持显示/隐藏）
    - 模型名称

  作为 SettingsDialog 的子板块使用，通过 emit 向父组件报告保存状态。
-->
<template>
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
          <svg v-if="!showApiKey" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
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
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { fetchLlmConfig, saveLlmConfig } from '../../api/index.js'

const props = defineProps({
  /** 父组件通知当前板块是否激活（用于触发加载） */
  active: { type: Boolean, default: false },
})

const emit = defineEmits(['toast', 'saving'])

// ---- 表单状态 ----
const form = reactive({
  base_url: 'https://api.deepseek.com',
  api_key: '',
  model_name: 'deepseek-v4-flash',
})
const hasApiKey = ref(false)
const showApiKey = ref(false)

// ---- 板块激活时加载配置 ----
watch(() => props.active, async (newVal) => {
  if (!newVal) return
  try {
    const config = await fetchLlmConfig()
    form.base_url = config.base_url
    form.model_name = config.model_name
    form.api_key = ''
    hasApiKey.value = config.has_api_key
  } catch (e) {
    emit('toast', e.message, 'error')
  }
}, { immediate: true })

/**
 * 保存配置（由父组件调用）
 * @returns {Promise<boolean>} 是否成功
 */
async function save() {
  emit('saving', true)
  try {
    const msg = await saveLlmConfig({
      base_url: form.base_url.trim(),
      api_key: form.api_key.trim(),
      model_name: form.model_name.trim(),
    })
    emit('toast', msg || '配置已保存并立即生效', 'success')
    return true
  } catch (e) {
    emit('toast', e.message, 'error')
    return false
  } finally {
    emit('saving', false)
  }
}

// 暴露 save 方法给父组件
defineExpose({ save })
</script>

<style scoped>
.settings-section {
  animation: section-fade-in 0.25s ease-out;
}

@keyframes section-fade-in {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
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
  color: #0D9488;
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
  color: var(--text-secondary);
  margin-top: 6px;
  line-height: 1.4;
}

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
</style>
