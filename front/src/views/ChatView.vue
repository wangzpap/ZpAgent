<!--
  ChatView.vue — 聊天主视图
  包含消息列表、输入框和底部工具选择器
-->
<template>
  <!-- 消息列表区域 -->
  <div class="messages-container" ref="messagesContainer">
    <!-- 空状态 -->
    <div v-if="messages.length === 0" class="empty-state">
      <div class="icon">&gt;_</div>
      <p>ReAct Agent Ready</p>
      <p>选择工具，输入问题，观察推理过程</p>
    </div>

    <!-- 消息列表 -->
    <ChatMessage
      v-for="(msg, idx) in messages"
      :key="idx"
      :message="msg"
      :is-latest="idx === messages.length - 1 && isLoading"
    />
  </div>

  <!-- 输入区域 -->
  <div class="input-area">
    <div class="input-card">
      <!-- 文本输入行 -->
      <div class="input-row">
        <textarea
          ref="inputRef"
          v-model="inputText"
          placeholder="输入消息..."
          rows="1"
          @keydown="handleKeydown"
          @input="autoResize"
          :disabled="isLoading"
        />
        <button
          class="send-btn"
          @click="handleSend"
          :disabled="isLoading || !inputText.trim()"
        >
          <span v-if="isLoading" class="typing-indicator inline">
            <span></span><span></span><span></span>
          </span>
          <span v-else>发送</span>
        </button>
      </div>

      <!-- 底部栏：工具选择器 + 快捷键提示 -->
      <div class="input-footer">
        <ToolSelector
          :tools="tools"
          :selected="selectedTools"
          @toggle="onToggleTool"
        />
        <span class="hint">Enter 发送 &middot; Shift+Enter 换行</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'
import ChatMessage from '../components/ChatMessage.vue'
import ToolSelector from '../components/ToolSelector.vue'

const props = defineProps({
  messages:      { type: Array, default: () => [] },
  isLoading:     { type: Boolean, default: false },
  tools:         { type: Array, default: () => [] },
  selectedTools: { type: Array, default: () => [] },
})

const emit = defineEmits(['send', 'toggle-tool'])

const inputText = ref('')
const messagesContainer = ref(null)
const inputRef = ref(null)

// 消息变化时自动滚动
watch(
  () => props.messages,
  () => nextTick(scrollToBottom),
  { deep: true }
)

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

function handleSend() {
  const text = inputText.value.trim()
  if (!text || props.isLoading) return
  emit('send', text)
  inputText.value = ''
  nextTick(() => {
    if (inputRef.value) inputRef.value.style.height = 'auto'
  })
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function autoResize() {
  const el = inputRef.value
  if (el) {
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }
}

function onToggleTool(name) {
  emit('toggle-tool', name)
}
</script>
