<!--
  ConfirmDialog.vue — 通用二次确认弹窗

  用于危险操作（如删除会话）前的二次确认。
  支持自定义标题、描述、按钮文案和按钮样式。

  Props:
    visible     - 是否显示弹窗
    title       - 弹窗标题
    message     - 弹窗描述文案
    confirmText - 确认按钮文案（默认"确认"）
    cancelText  - 取消按钮文案（默认"取消"）
    danger      - 是否为危险操作样式（确认按钮变红）

  Events:
    confirm - 用户点击确认按钮
    cancel  - 用户点击取消按钮或遮罩层
-->
<template>
  <Teleport to="body">
    <Transition name="confirm-dialog">
      <div v-if="visible" class="confirm-overlay" @click.self="$emit('cancel')">
        <div class="confirm-dialog">
          <!-- 顶部警告图标 -->
          <div class="confirm-icon-wrap" :class="{ danger }">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/>
              <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
          </div>

          <h3 class="confirm-title">{{ title }}</h3>
          <p class="confirm-message">{{ message }}</p>

          <div class="confirm-actions">
            <button class="confirm-cancel-btn" @click="$emit('cancel')">
              {{ cancelText }}
            </button>
            <button
              class="confirm-ok-btn"
              :class="{ danger }"
              @click="$emit('confirm')"
            >
              {{ confirmText }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
defineProps({
  visible:     { type: Boolean, default: false },
  title:       { type: String,  default: '确认操作' },
  message:     { type: String,  default: '此操作不可撤销，确定继续吗？' },
  confirmText: { type: String,  default: '确认' },
  cancelText:  { type: String,  default: '取消' },
  danger:      { type: Boolean, default: true },
})

defineEmits(['confirm', 'cancel'])
</script>

<style scoped>
.confirm-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  animation: confirm-overlay-in 0.2s ease-out;
}

@keyframes confirm-overlay-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}

.confirm-dialog {
  width: 380px;
  max-width: 90vw;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius);
  padding: 28px 28px 22px;
  text-align: center;
  box-shadow: var(--shadow-float);
  animation: confirm-dialog-in 0.28s var(--ease-out);
}

@keyframes confirm-dialog-in {
  from {
    opacity: 0;
    transform: translateY(16px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* Vue Transition 支持 */
.confirm-dialog-enter-active {
  transition: all 0.28s var(--ease-out);
}
.confirm-dialog-leave-active {
  transition: all 0.18s ease-in;
}
.confirm-dialog-enter-from,
.confirm-dialog-leave-to {
  opacity: 0;
}
.confirm-dialog-enter-from .confirm-dialog,
.confirm-dialog-leave-to .confirm-dialog {
  transform: translateY(16px) scale(0.96);
}

.confirm-icon-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  margin-bottom: 16px;
}

.confirm-icon-wrap.danger {
  background: rgba(239, 107, 107, 0.12);
  color: var(--danger);
  border: 1px solid rgba(239, 107, 107, 0.20);
}

.confirm-icon-wrap:not(.danger) {
  background: var(--accent-dim);
  color: var(--accent);
  border: 1px solid var(--border-accent);
}

.confirm-title {
  font-size: 16px;
  font-weight: 650;
  color: var(--text-primary);
  margin-bottom: 8px;
  letter-spacing: 0.2px;
}

.confirm-message {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 24px;
  word-break: break-all;
}

.confirm-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}

.confirm-cancel-btn {
  flex: 1;
  padding: 10px 20px;
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

.confirm-cancel-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-color: var(--border-light);
}

.confirm-ok-btn {
  flex: 1;
  padding: 10px 20px;
  border: none;
  border-radius: var(--radius-xs);
  font-size: 13px;
  font-weight: 600;
  font-family: var(--font-ui);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.confirm-ok-btn.danger {
  background: var(--danger);
  color: #fff;
  box-shadow: 0 2px 10px rgba(239, 107, 107, 0.25);
}

.confirm-ok-btn.danger:hover {
  background: #d94545;
  box-shadow: 0 4px 18px rgba(239, 107, 107, 0.35);
  transform: translateY(-1px);
}

.confirm-ok-btn:not(.danger) {
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-hover) 100%);
  color: var(--bg-base);
  box-shadow: 0 2px 10px var(--accent-glow);
}

.confirm-ok-btn:not(.danger):hover {
  box-shadow: 0 4px 18px var(--accent-glow);
  transform: translateY(-1px);
}
</style>
