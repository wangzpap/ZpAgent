<!--
  ChatMessage.vue — 单条消息组件
  支持用户消息 / 助手消息，助手消息展示 ReAct 思考过程
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
      <!-- 角色标签 -->
      <div class="role-label" :class="message.role">
        {{ message.role === 'user' ? 'You' : 'Agent' }}
      </div>

      <!-- 时间线片段（助手消息） -->
      <template v-if="message.role === 'assistant' && message.segments">
        <template v-for="(seg, idx) in message.segments" :key="idx">
          <!-- 文本片段（支持 Markdown） -->
          <div
            v-if="seg.type === 'text' && seg.content"
            class="message-bubble assistant md-content"
            v-html="renderMd(seg.content)"
          ></div>
          <!-- 工具调用片段 -->
          <div v-else-if="seg.type === 'tool_call'" class="thinking-block">
            <div class="step-label">
              <span class="tool-name">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
                </svg>
                {{ toolDisplayName(seg.tool) }}
              </span>
              <span v-if="seg.args" class="step-args">
                {{ JSON.stringify(seg.args) }}
              </span>
            </div>
            <div v-if="seg.observation" class="observation">
              <div class="observation-label">Result</div>
              {{ seg.observation }}
            </div>
          </div>
        </template>
      </template>

      <!-- 用户消息正文 -->
      <div
        v-if="message.role === 'user' && message.content"
        class="message-bubble"
        :class="message.role"
      >
        {{ message.content }}
      </div>

      <!-- 加载动画 -->
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

// 配置 marked：GFM 模式 + 换行转 <br>
marked.setOptions({
  breaks: true,
  gfm: true,
})

defineProps({
  message:  { type: Object, required: true },
  isLatest: { type: Boolean, default: false },
})

function renderMd(text) {
  if (!text) return ''
  return marked.parse(text)
}

function toolDisplayName(name) {
  const map = {
    get_location: '当前位置',
    get_datetime: '当前时间',
    get_weather: '天气查询',
  }
  return map[name] || name
}
</script>

<style scoped>
.message-body {
  flex: 1;
  min-width: 0;
}

.role-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  margin-bottom: 6px;
  color: var(--text-muted);
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
.tool-name {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.step-args {
  opacity: 0.5;
  font-family: var(--font-mono);
  font-size: 11px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.observation-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--accent);
  margin-bottom: 6px;
  opacity: 0.7;
}

/* ---- 行内加载指示器（发送按钮） ---- */
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
  margin: 0 0 0.6em;
}

.message-bubble.assistant.md-content :deep(p:last-child) {
  margin-bottom: 0;
}

.message-bubble.assistant.md-content :deep(h1),
.message-bubble.assistant.md-content :deep(h2),
.message-bubble.assistant.md-content :deep(h3),
.message-bubble.assistant.md-content :deep(h4) {
  margin: 0.8em 0 0.4em;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
}

.message-bubble.assistant.md-content :deep(h1) { font-size: 1.3em; }
.message-bubble.assistant.md-content :deep(h2) { font-size: 1.15em; }
.message-bubble.assistant.md-content :deep(h3) { font-size: 1.05em; }

.message-bubble.assistant.md-content :deep(ul),
.message-bubble.assistant.md-content :deep(ol) {
  margin: 0.4em 0;
  padding-left: 1.6em;
}

.message-bubble.assistant.md-content :deep(li) {
  margin: 0.2em 0;
}

.message-bubble.assistant.md-content :deep(code) {
  background: rgba(255, 255, 255, 0.08);
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 0.88em;
}

.message-bubble.assistant.md-content :deep(pre) {
  background: rgba(0, 0, 0, 0.3);
  padding: 12px 16px;
  border-radius: var(--radius-xs);
  overflow-x: auto;
  margin: 0.6em 0;
  border: 1px solid var(--border);
}

.message-bubble.assistant.md-content :deep(pre code) {
  background: none;
  padding: 0;
  font-size: 0.85em;
}

.message-bubble.assistant.md-content :deep(strong) {
  color: var(--text-primary);
  font-weight: 600;
}

.message-bubble.assistant.md-content :deep(a) {
  color: var(--accent);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.message-bubble.assistant.md-content :deep(blockquote) {
  border-left: 3px solid var(--accent);
  padding-left: 12px;
  margin: 0.6em 0;
  color: var(--text-secondary);
  opacity: 0.85;
}

.message-bubble.assistant.md-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: 1em 0;
}

.message-bubble.assistant.md-content :deep(table) {
  border-collapse: collapse;
  margin: 0.6em 0;
  width: 100%;
  font-size: 0.9em;
}

.message-bubble.assistant.md-content :deep(th),
.message-bubble.assistant.md-content :deep(td) {
  border: 1px solid var(--border-light);
  padding: 6px 12px;
  text-align: left;
}

.message-bubble.assistant.md-content :deep(th) {
  background: var(--bg-hover);
  font-weight: 600;
}
</style>
