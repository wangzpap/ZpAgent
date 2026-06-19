<!--
  ChatView.vue — 聊天主视图

  包含三个区域：
    1. 消息列表（自动滚动到底部）
    2. 输入框（支持 Enter 发送、Shift+Enter 换行、自动高度调整）
    3. 底部栏（工具选择器 + 快捷键提示）
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
          <!-- 加载中显示三点动画，否则显示"发送" -->
          <span v-if="isLoading" class="typing-indicator inline">
            <span></span><span></span><span></span>
          </span>
          <span v-else>发送</span>
        </button>
      </div>

      <!-- 底部栏：工具选择器 + 快捷键提示 -->
      <div class="input-footer">
        <!-- 工具选择器：透传 toggle 和 reload 事件给父组件 -->
        <ToolSelector
          :tools="tools"
          :selected="selectedTools"
          @toggle="onToggleTool"
          @reload="$emit('reload-tools')"
        />
        <div class="input-footer-right">
          <!-- 清空对话按钮：仅在有活跃会话且有消息时显示，内联二次确认 -->
          <button
            v-if="conversationId && messages.length > 0"
            class="clear-btn"
            :class="{ 'confirm-state': isConfirmingClear }"
            @click="handleClearClick"
            :title="isConfirmingClear ? '再次点击确认清空' : '清空当前对话上下文'"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
            <span>{{ isConfirmingClear ? '确认清空？' : '清空上下文' }}</span>
          </button>
          <span class="hint">Enter 发送 &middot; Shift+Enter 换行</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'
import ChatMessage from '../components/ChatMessage.vue'
import ToolSelector from '../components/ToolSelector.vue'

const props = defineProps({
  messages:        { type: Array, default: () => [] },
  isLoading:       { type: Boolean, default: false },
  tools:           { type: Array, default: () => [] },
  selectedTools:   { type: Array, default: () => [] },
  conversationId:  { type: String, default: null },
})

// 事件：send（发送消息）、toggle-tool（切换工具选中）、reload-tools（刷新 MCP 工具）、clear-history（清空对话上下文）
const emit = defineEmits(['send', 'toggle-tool', 'reload-tools', 'clear-history'])

const inputText = ref('')
const messagesContainer = ref(null)
const inputRef = ref(null)

// 消息变化时自动滚动到底部
watch(
  () => props.messages,
  () => nextTick(scrollToBottom),
  { deep: true }
)

/** 滚动消息列表到底部 */
function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

/** 发送消息（非空且非加载中时） */
function handleSend() {
  const text = inputText.value.trim()
  if (!text || props.isLoading) return
  emit('send', text)
  inputText.value = ''
  // 发送后重置输入框高度
  nextTick(() => {
    if (inputRef.value) inputRef.value.style.height = 'auto'
  })
}

/** 键盘事件：Enter 发送，Shift+Enter 换行 */
function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

/** 输入框自动高度调整（最大 120px） */
function autoResize() {
  const el = inputRef.value
  if (el) {
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }
}

/** 工具选择切换（透传给父组件） */
function onToggleTool(name) {
  emit('toggle-tool', name)
}

// ---- 清空按钮二次确认 ----
const isConfirmingClear = ref(false)
let clearConfirmTimer = null

/**
 * 清空按钮点击处理（内联二次确认）
 *
 * 第一次点击：按钮变为红色"确认清空？"状态，启动 3 秒倒计时
 * 3 秒内再次点击：真正触发清空操作
 * 3 秒内未点击：自动恢复原始状态
 */
function handleClearClick() {
  if (isConfirmingClear.value) {
    // 二次点击确认 → 执行清空
    clearTimeout(clearConfirmTimer)
    isConfirmingClear.value = false
    emit('clear-history')
  } else {
    // 首次点击 → 进入确认状态
    isConfirmingClear.value = true
    clearConfirmTimer = setTimeout(() => {
      isConfirmingClear.value = false
    }, 3000)
  }
}
</script>
