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

      <!-- 用户消息正文 -->
      <div
        v-if="message.role === 'user' && message.content"
        class="message-bubble"
        :class="message.role"
      >
        {{ message.content }}
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
import { marked } from 'marked'
import { toolDisplayName } from '../utils/index.js'

// 配置 marked：GFM 模式 + 换行转 <br>
marked.setOptions({ breaks: true, gfm: true })

defineProps({
  message:  { type: Object, required: true },
  isLatest: { type: Boolean, default: false },
})

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
</style>
