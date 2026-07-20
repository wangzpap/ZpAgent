<!--
  ChatMessage.vue — 单条消息组件

  支持两种角色：
    - user: 用户消息，显示在右侧，琥珀色渐变气泡
    - assistant: 助手消息，显示在左侧，支持 Markdown 文本 + 工具调用时间线

  助手消息的 segments 结构：
    - text: 文本片段，使用 marked 渲染 Markdown
    - tool_call: 工具调用片段，显示工具名、参数、执行结果
-->
<template>
  <div class="message-wrapper" :class="message.role">
    <!-- 头像 -->
    <div class="avatar" :class="message.role">
      <template v-if="message.role === 'user'">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 12c2.7 0 5-2.3 5-5s-2.3-5-5-5-5 2.3-5 5 2.3 5 5 5zm0 2c-3.3 0-10 1.7-10 5v2h20v-2c0-3.3-6.7-5-10-5z"/>
        </svg>
      </template>
      <template v-else>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5z"/>
          <path d="M2 17l10 5 10-5"/>
          <path d="M2 12l10 5 10-5"/>
        </svg>
      </template>
    </div>

    <!-- 消息主体 -->
    <div class="message-body">
      <div class="role-label" :class="message.role">
        {{ message.role === 'user' ? 'You' : 'Agent' }}
      </div>

      <!-- 助手消息：按时间线渲染 segments -->
      <template v-if="message.role === 'assistant' && message.segments">
        <div class="segments-container">
        <template v-for="(seg, idx) in message.segments" :key="idx">
          <!-- 文本片段（Markdown 渲染） -->
          <div
            v-if="seg.type === 'text' && seg.content"
            class="message-bubble assistant md-content"
            v-html="renderMd(seg.content)"
          ></div>
          <!-- 工具调用片段 -->
          <div v-else-if="seg.type === 'tool_call'" class="thinking-block" :class="{ 'is-loading': seg.observation == null }">
            <div class="step-label">
              <span class="tool-name">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M14.7 6.3a1 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
                </svg>
                {{ toolDisplayName(seg.tool) }}
              </span>
              <span v-if="seg.args" class="step-args">
                {{ JSON.stringify(seg.args) }}
              </span>
              <!-- 工具执行中：显示加载动画 -->
              <span v-if="seg.observation == null" class="tool-loading">
                <span class="loading-dot"></span>
                <span class="loading-dot"></span>
                <span class="loading-dot"></span>
              </span>
            </div>
            <!-- 工具执行完毕：显示结果 -->
            <div v-if="seg.observation" class="observation">
              <div class="observation-label">Result</div>
              {{ seg.observation }}
            </div>
          </div>
        </template>
        </div>
      </template>

      <!-- 操作按钮区（hover 气泡时显示，仅助手消息渲染，避免用户消息下出现空 div 占位） -->
      <div v-if="message.role === 'assistant' && assistantText" class="copy-btn-area">
        <!-- 一键复制按钮 -->
        <button class="copy-btn" :class="{ copied }" @click.stop="copyContent" :title="copied ? '已复制' : '复制回复内容'">
          <template v-if="!copied">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
            <span>复制</span>
          </template>
          <template v-else>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            <span>已复制</span>
          </template>
        </button>
      </div>

      <!-- 用户消息正文 -->
      <div
        v-if="message.role === 'user' && message.content"
        class="message-bubble"
        :class="message.role"
      >
        {{ message.content }}
      </div>

      <!-- 用户消息删除按钮（气泡外右下角，hover 消息行时显示） -->
      <div
        v-if="message.role === 'user' && message.id && !isTempId(message.id)"
        class="user-delete-row"
      >
        <!-- 回退按钮 -->
        <div class="user-delete-area" :class="{ 'has-popover': showRewindPopover }">
          <button
            class="user-action-btn"
            :class="{ active: showRewindPopover }"
            @click.stop="toggleRewindPopover"
            title="回退到此消息之前"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="1 4 1 10 7 10"/>
              <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
            </svg>
            <span>回退</span>
          </button>

          <div v-if="showRewindPopover" class="delete-popover" @click.stop>
            <div class="popover-warn">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="1 4 1 10 7 10"/>
                <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
              </svg>
              <span>将把该消息重新填入输入框，并删除该消息及其之后的所有消息，此操作不可恢复</span>
            </div>
            <div class="popover-actions">
              <button class="popover-btn confirm" @click.stop="doRewind">确认回退</button>
              <button class="popover-btn cancel" @click.stop="cancelRewindPopover">取消</button>
            </div>
          </div>
        </div>

        <!-- 删除按钮 -->
        <div class="user-delete-area" :class="{ 'has-popover': showDeletePopover }">
          <button
            class="user-action-btn"
            :class="{ active: showDeletePopover }"
            @click.stop="toggleDeletePopover"
            title="删除此轮对话"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            </svg>
            <span>删除</span>
          </button>

          <div v-if="showDeletePopover" class="delete-popover" @click.stop>
            <div class="popover-warn">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
              <span>将删除该消息及其之后的所有消息，且无法恢复</span>
            </div>
            <div class="popover-actions">
              <button class="popover-btn confirm" @click.stop="doDelete">确认删除</button>
              <button class="popover-btn cancel" @click.stop="cancelDeletePopover">取消</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 加载动画（仅最新一条空助手消息显示） -->
      <div
        v-if="message.role === 'assistant' && (!message.segments || message.segments.length === 0) && isLatest"
        class="message-bubble assistant"
      >
        <div class="typing-indicator">
          <span></span><span></span><span></span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { marked } from 'marked'
import { toolDisplayName } from '../utils/index.js'

// 配置 marked：GFM 模式 + 换行转 <br>
marked.setOptions({ breaks: true, gfm: true })

const props = defineProps({
  message:    { type: Object, required: true },
  isLatest:   { type: Boolean, default: false },
})

const emit = defineEmits(['delete', 'rewind'])

/** 提取助手消息中的纯文本内容（用于复制） */
const assistantText = computed(() => {
  if (!props.message.segments) return ''
  return props.message.segments
    .filter(s => s.type === 'text' && s.content)
    .map(s => s.content)
    .join('\n')
})

const copied = ref(false)

/** 一键复制助手回复内容到剪贴板 */
async function copyContent() {
  try {
    await navigator.clipboard.writeText(assistantText.value)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    // 降级：静默失败
  }
}

const showDeletePopover = ref(false)

/** 判断是否为前端生成的临时 ID（以 temp_ 开头） */
function isTempId(id) {
  return id && id.startsWith('temp_')
}

/** 切换删除确认弹窗（打开 delete 时关闭 rewind） */
function toggleDeletePopover() {
  showRewindPopover.value = false
  showDeletePopover.value = !showDeletePopover.value
}

/** 取消删除 */
function cancelDeletePopover() {
  showDeletePopover.value = false
}

/** 确认删除 */
function doDelete() {
  showDeletePopover.value = false
  emit('delete', props.message.id)
}

// ---- 回退功能（rewind） ----
const showRewindPopover = ref(false)

/** 切换回退确认弹窗（打开 rewind 时关闭 delete） */
function toggleRewindPopover() {
  showDeletePopover.value = false
  showRewindPopover.value = !showRewindPopover.value
}

/** 取消回退 */
function cancelRewindPopover() {
  showRewindPopover.value = false
}

/** 确认回退：将消息内容回填到输入框，并删除该消息及之后所有消息 */
function doRewind() {
  showRewindPopover.value = false
  emit('rewind', { id: props.message.id, content: props.message.content })
}

/** 渲染 Markdown 文本为 HTML */
function renderMd(text) {
  if (!text) return ''
  return marked.parse(text)
}
</script>

<style scoped>
.message-body {
  flex: 1;
  min-width: 0;
}

/* segments 容器：用 flex + gap 统一控制工具调用框与文本气泡的间距 */
.segments-container {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.role-label {
  font-size: 10.5px;
  font-weight: 650;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 7px;
  color: var(--text-secondary);
}

.role-label.user {
  text-align: right;
}

.message-wrapper.user .message-body {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

/* ---- 工具调用片段 ---- */
/* 使用 .step-label .tool-name 提高优先级，避免被全局 :first-child 规则覆盖颜色 */
.step-label .tool-name {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 11.5px;
  font-weight: 600;
  background: var(--accent-dim);
  padding: 3px 10px;
  border-radius: var(--radius-xxs);
  border: 1px solid var(--border-accent);
}

.step-args {
  opacity: 0.65;
  font-family: var(--font-mono);
  font-size: 10.5px;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ---- 工具调用加载动画 ---- */
.tool-loading {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-left: 4px;
}

.loading-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--accent);
  animation: tool-loading-pulse 1.2s ease-in-out infinite;
}

.loading-dot:nth-child(2) { animation-delay: 0.15s; }
.loading-dot:nth-child(3) { animation-delay: 0.3s; }

@keyframes tool-loading-pulse {
  0%, 60%, 100% {
    opacity: 0.25;
    transform: scale(0.75);
  }
  30% {
    opacity: 1;
    transform: scale(1.1);
  }
}

/* 加载中的工具调用框：微妙的边框动画 */
.thinking-block.is-loading {
  border-color: rgba(232, 187, 94, 0.25);
}

.observation-label {
  font-size: 9.5px;
  font-weight: 650;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--accent);
  margin-bottom: 7px;
  opacity: 0.9;
}

/* ---- 行内加载指示器 ---- */
.typing-indicator.inline {
  display: inline-flex;
  gap: 3px;
  padding: 0;
  vertical-align: middle;
}

.typing-indicator.inline span {
  width: 4px;
  height: 4px;
}

/* ---- Markdown 渲染样式 ---- */
.message-bubble.assistant.md-content {
  white-space: normal;
  word-break: break-word;
}

.message-bubble.assistant.md-content :deep(p) {
  margin: 0 0 0.7em;
}

.message-bubble.assistant.md-content :deep(p:last-child) {
  margin-bottom: 0;
}

.message-bubble.assistant.md-content :deep(h1),
.message-bubble.assistant.md-content :deep(h2),
.message-bubble.assistant.md-content :deep(h3),
.message-bubble.assistant.md-content :deep(h4) {
  margin: 1em 0 0.45em;
  font-weight: 650;
  color: var(--text-primary);
  line-height: 1.4;
}

.message-bubble.assistant.md-content :deep(h1) { font-size: 1.35em; }
.message-bubble.assistant.md-content :deep(h2) { font-size: 1.18em; }
.message-bubble.assistant.md-content :deep(h3) { font-size: 1.06em; }

.message-bubble.assistant.md-content :deep(ul),
.message-bubble.assistant.md-content :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.6em;
}

.message-bubble.assistant.md-content :deep(li) {
  margin: 0.25em 0;
  line-height: 1.7;
}

.message-bubble.assistant.md-content :deep(code) {
  background: rgba(255, 255, 255, 0.07);
  padding: 0.18em 0.45em;
  border-radius: 5px;
  font-family: var(--font-mono);
  font-size: 0.87em;
  border: 1px solid rgba(255,255,255,0.04);
}

.message-bubble.assistant.md-content :deep(pre) {
  background: rgba(0, 0, 0, 0.30);
  padding: 14px 18px;
  border-radius: var(--radius-xs);
  overflow-x: auto;
  margin: 0.7em 0;
  border: 1px solid var(--border);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
}

.message-bubble.assistant.md-content :deep(pre code) {
  background: none;
  padding: 0;
  font-size: 0.84em;
  border: none;
}

.message-bubble.assistant.md-content :deep(strong) {
  color: var(--text-primary);
  font-weight: 650;
}

.message-bubble.assistant.md-content :deep(a) {
  color: var(--accent);
  text-decoration: underline;
  text-underline-offset: 3px;
  text-decoration-color: rgba(232,187,94,0.35);
  transition: text-decoration-color 0.2s;
}

.message-bubble.assistant.md-content :deep(a:hover) {
  text-decoration-color: var(--accent);
}

.message-bubble.assistant.md-content :deep(blockquote) {
  border-left: 3px solid var(--accent);
  padding-left: 14px;
  margin: 0.7em 0;
  color: var(--text-secondary);
  opacity: 0.88;
}

.message-bubble.assistant.md-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: 1.2em 0;
}

.message-bubble.assistant.md-content :deep(table) {
  border-collapse: collapse;
  margin: 0.7em 0;
  width: 100%;
  font-size: 0.9em;
}

.message-bubble.assistant.md-content :deep(th),
.message-bubble.assistant.md-content :deep(td) {
  border: 1px solid var(--border-light);
  padding: 7px 14px;
  text-align: left;
}

.message-bubble.assistant.md-content :deep(th) {
  background: var(--bg-hover);
  font-weight: 600;
}

/* ---- 一键复制按钮（hover 气泡时显示） ---- */
.copy-btn-area {
  margin-top: 6px;
  display: flex;
  align-items: center;
}

.copy-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-xxs);
  color: var(--text-muted);
  font-size: 11px;
  font-family: var(--font-ui);
  cursor: pointer;
  transition: all 0.2s var(--ease-out);
  opacity: 0;
  transform: translateY(2px);
}

/* hover 消息行时显示复制按钮 */
.message-wrapper:hover .copy-btn {
  opacity: 1;
  transform: translateY(0);
}

.copy-btn:hover {
  color: var(--accent);
  border-color: var(--border-accent);
  background: var(--accent-dim);
}

/* 复制成功态 */
.copy-btn.copied {
  color: var(--success);
  border-color: rgba(74, 222, 128, 0.30);
  background: rgba(74, 222, 128, 0.10);
  opacity: 1;
}

/* ---- 用户消息删除按钮（气泡外右下角） ---- */
.user-delete-row {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  margin-top: 4px;
  position: relative;
}

.user-delete-area {
  position: relative;
}

.user-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-xxs);
  color: var(--text-muted);
  font-size: 11px;
  font-family: var(--font-ui);
  cursor: pointer;
  transition: all 0.2s var(--ease-out);
  opacity: 0;
  transform: translateY(2px);
}

/* hover 消息行时显示操作按钮 */
.message-wrapper:hover .user-action-btn {
  opacity: 1;
  transform: translateY(0);
}

.user-action-btn:hover,
.user-action-btn.active {
  color: var(--danger);
  border-color: rgba(239, 68, 68, 0.30);
  background: rgba(239, 68, 68, 0.10);
}

/* ---- 删除确认弹窗 ---- */
.delete-popover {
  position: absolute;
  right: 0;
  bottom: calc(100% + 8px);
  width: 280px;
  background: var(--bg-card);
  border: 1px solid var(--border-danger, rgba(239, 68, 68, 0.30));
  border-radius: var(--radius-xs);
  padding: 14px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.40);
  z-index: 20;
  animation: popover-in 0.18s var(--ease-out);
}

@keyframes popover-in {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}

.popover-warn {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  font-size: 12.5px;
  color: var(--text-primary);
  line-height: 1.6;
  margin-bottom: 12px;
}

.popover-warn svg {
  flex-shrink: 0;
  color: var(--danger);
  margin-top: 1px;
}

.popover-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.popover-btn {
  padding: 5px 14px;
  border-radius: var(--radius-xxs);
  font-size: 12px;
  font-family: var(--font-ui);
  cursor: pointer;
  transition: all 0.15s;
  border: 1px solid transparent;
}

.popover-btn.confirm {
  background: var(--danger);
  color: #fff;
  border-color: var(--danger);
}

.popover-btn.confirm:hover {
  opacity: 0.85;
}

.popover-btn.cancel {
  background: transparent;
  color: var(--text-secondary);
  border-color: var(--border);
}

.popover-btn.cancel:hover {
  border-color: var(--text-muted);
  color: var(--text-primary);
}

</style>
