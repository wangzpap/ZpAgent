<!--
  CompressionSettings.vue — 对话压缩（摘要中间件）配置板块

  配置 SummarizationMiddleware 的参数：
    - 是否启用摘要压缩（开关）
    - 摘要专用模型（可选，空=复用主模型）
    - 触发摘要的 token 阈值
    - 摘要后保留最近消息数

  作为 SettingsDialog 的子板块使用，通过 emit 向父组件报告保存状态。
-->
<template>
  <div class="settings-section">
    <div class="section-label">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
        <polyline points="7.5 4.21 12 6.81 16.5 4.21"/>
        <polyline points="7.5 19.79 7.5 14.6 3 12"/>
        <polyline points="21 12 16.5 14.6 16.5 19.79"/>
        <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
        <line x1="12" y1="22.08" x2="12" y2="12"/>
      </svg>
      对话压缩
    </div>

    <!-- 功能说明 -->
    <p class="section-desc">
      开启后，当对话历史的 token 数超过阈值时，自动将早期消息压缩为摘要，
      减少上下文占用，适合长对话场景。
    </p>

    <!-- 启用开关 -->
    <div class="form-group switch-group">
      <div class="switch-row">
        <div class="switch-info">
          <label class="form-label no-margin">启用摘要压缩</label>
          <span class="form-hint no-margin">全局生效，应用于所有会话</span>
        </div>
        <button
          class="switch-toggle"
          :class="{ active: form.summary_enabled }"
          @click="form.summary_enabled = !form.summary_enabled"
          role="switch"
          :aria-checked="form.summary_enabled"
        >
          <span class="switch-thumb"></span>
        </button>
      </div>
    </div>

    <!-- 以下字段在关闭时 disabled -->
    <fieldset class="fields-fieldset" :disabled="!form.summary_enabled">
      <!-- 摘要模型 -->
      <div class="form-group">
        <label class="form-label">摘要模型</label>
        <input
          v-model="form.summary_model"
          class="form-input"
          type="text"
          placeholder="留空则复用主模型"
          spellcheck="false"
        />
        <span class="form-hint">
          可指定更轻量的模型专门做摘要（如 deepseek-v4-flash），留空则使用主模型
        </span>
      </div>

      <!-- Token 阈值 -->
      <div class="form-group">
        <label class="form-label">触发阈值（tokens）</label>
        <input
          v-model.number="form.summary_max_tokens"
          class="form-input"
          type="number"
          min="1000"
          step="500"
          placeholder="4000"
        />
        <span class="form-hint">
          历史消息的 token 总量超过此值时触发摘要压缩
        </span>
      </div>

      <!-- 保留消息数 -->
      <div class="form-group">
        <label class="form-label">保留最近消息数</label>
        <input
          v-model.number="form.summary_messages_to_keep"
          class="form-input"
          type="number"
          min="4"
          step="2"
          placeholder="20"
        />
        <span class="form-hint">
          摘要后保留最近 N 条消息不动，更早的消息被压缩为摘要文本
        </span>
      </div>
    </fieldset>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue'
import { fetchMiddlewareConfig, saveMiddlewareConfig } from '../../api/index.js'

const props = defineProps({
  active: { type: Boolean, default: false },
})

const emit = defineEmits(['toast', 'saving'])

// ---- 表单状态 ----
const form = reactive({
  summary_enabled: false,
  summary_model: '',
  summary_max_tokens: 4000,
  summary_messages_to_keep: 20,
})

// ---- 板块激活时加载配置 ----
watch(() => props.active, async (newVal) => {
  if (!newVal) return
  try {
    const config = await fetchMiddlewareConfig()
    form.summary_enabled = config.summary_enabled
    form.summary_model = config.summary_model
    form.summary_max_tokens = config.summary_max_tokens
    form.summary_messages_to_keep = config.summary_messages_to_keep
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
    const msg = await saveMiddlewareConfig({
      summary_enabled: form.summary_enabled,
      summary_model: form.summary_model.trim(),
      summary_max_tokens: form.summary_max_tokens || 4000,
      summary_messages_to_keep: form.summary_messages_to_keep || 20,
    })
    emit('toast', msg || '中间件配置已保存并立即生效', 'success')
    return true
  } catch (e) {
    emit('toast', e.message, 'error')
    return false
  } finally {
    emit('saving', false)
  }
}

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
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

.section-label svg {
  opacity: 0.7;
}

.section-desc {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 20px;
  padding: 10px 12px;
  background: var(--bg-hover);
  border-radius: var(--radius-xs);
  border: 1px solid var(--border);
}

/* ---- 开关组 ---- */
.switch-group {
  margin-bottom: 20px;
}

.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.switch-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-label.no-margin {
  margin-bottom: 0;
}

.form-hint.no-margin {
  margin-top: 0;
}

/* ---- Toggle Switch ---- */
.switch-toggle {
  position: relative;
  width: 44px;
  height: 24px;
  border-radius: 12px;
  border: 1px solid var(--border-light);
  background: var(--bg-input);
  cursor: pointer;
  transition: all 0.25s ease;
  flex-shrink: 0;
  padding: 0;
}

.switch-toggle.active {
  background: var(--accent);
  border-color: var(--accent);
}

.switch-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--text-muted);
  transition: all 0.25s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.switch-toggle.active .switch-thumb {
  left: 22px;
  background: #fff;
}

/* ---- 字段区域（disabled 时半透明） ---- */
.fields-fieldset {
  border: none;
  padding: 0;
  margin: 0;
  transition: opacity 0.25s ease;
}

.fields-fieldset:disabled {
  opacity: 0.4;
  pointer-events: none;
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
  color: #0D9488;
  margin-bottom: 8px;
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
</style>
