<!--
  ChatView.vue — 聊天主视图

  包含三个区域：
    1. 消息列表（自动滚动到底部）
    2. 输入框（支持 Enter 发送、Shift+Enter 换行、自动高度调整）
    3. 底部栏（工具选择器 + 快捷键提示）
-->
<template>
  <!-- 消息区域外壳：wrapper 提供定位上下文，按钮相对它固定于可视区底部，
       不随 messages-container 滚动 -->
  <div class="messages-wrapper">
    <!-- 消息列表区域（可滚动） -->
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
        :key="msg.id || idx"
        :message="msg"
        :is-latest="idx === messages.length - 1 && isLoading"
        @delete="(msgId) => $emit('delete-message', msgId)"
        @rewind="(payload) => $emit('rewind', payload)"
      />
    </div>

    <!-- 回到底部浮动按钮：定位在 wrapper 可视区底部，不随消息滚动 -->
    <button
      class="scroll-to-bottom-btn"
      :class="{ visible: userScrolledUp }"
      @click="handleScrollToBottomClick"
      title="回到底部"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </button>
  </div>

  <!-- HITL 审批面板：放在消息列表和输入框之间 -->
  <ApprovalPanel
    v-if="pendingActions"
    :actions="pendingActions"
    @submit="(decisions) => $emit('approval-submit', decisions)"
  />

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
import { ref, nextTick, watch, onMounted, onBeforeUnmount } from 'vue'
import ChatMessage from '../components/ChatMessage.vue'
import ToolSelector from '../components/ToolSelector.vue'
import ApprovalPanel from '../components/ApprovalPanel.vue'

const props = defineProps({
  messages:        { type: Array, default: () => [] },
  isLoading:       { type: Boolean, default: false },
  tools:           { type: Array, default: () => [] },
  selectedTools:   { type: Array, default: () => [] },
  conversationId:  { type: String, default: null },
  prefillText:     { type: Object, default: () => ({ text: '', ts: 0 }) },
  pendingActions:  { type: Array, default: null },
})

// 事件
const emit = defineEmits([
  'send', 'toggle-tool', 'reload-tools', 'clear-history',
  'delete-message', 'rewind', 'approval-submit',
])

const inputText = ref('')
const messagesContainer = ref(null)
const inputRef = ref(null)

// ---- 滚动行为 ----
// 用户是否已主动上滚（离开底部超过阈值）。为 true 时消息更新不再强制拉回底部，
// 避免打断用户阅读历史；此时显示"回到底部"浮动按钮供手动跳回。
const userScrolledUp = ref(false)
// 距底部多少像素以内视为"在底部"——150px 容忍一行工具卡片展开的高度变化。
const SCROLL_THRESHOLD = 150
// 停止滑动多久后重新评估按钮是否显示——滑动过程中按钮始终保持隐藏，
// 停止滚动 400ms 后若仍离开底部才重新浮现，避免遮挡正在阅读的内容。
const SCROLL_HIDE_DELAY = 400
// 程序触发 scrollToBottom（含 smooth 动画）期间，scroll 事件仍会持续触发。
// 此标志为 true 时 onScroll 跳过判定，防止动画中途被误判为"用户上滚"。
let isProgrammaticScroll = false
// 用户发送消息或切换会话时，下一次 watcher 应无视 userScrolledUp 强制滚回。
let forceScrollOnce = false
// 停止滚动后的延迟评估定时器（onBeforeUnmount 需清理，防止泄漏）。
let scrollHideTimer = null

/**
 * 滚动消息列表到底部。
 * @param {boolean} smooth - true 时使用 smooth 行为（按钮点击），false 瞬移（流式追加）。
 */
function scrollToBottom(smooth = false) {
  if (!messagesContainer.value) return
  isProgrammaticScroll = true
  // 点击按钮滚动时立即隐藏按钮，动画期间不再显示
  userScrolledUp.value = false
  if (smooth) {
    messagesContainer.value.scrollTo({
      top: messagesContainer.value.scrollHeight,
      behavior: 'smooth',
    })
    // smooth 滚动约 340ms 完成（CSS --transition-slow 300ms 级别），
    // 延时重置标志位确保期间 scroll 事件全部被忽略。
    setTimeout(() => {
      isProgrammaticScroll = false
      userScrolledUp.value = false
    }, 350)
  } else {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    // 瞬移后仅一帧即可到达底部，nextTick 重置即可。
    nextTick(() => { isProgrammaticScroll = false })
  }
}

/**
 * 消息列表 scroll 事件：
 * - 滑动过程中立即隐藏按钮（不阻塞视觉）
 * - 停止滑动 SCROLL_HIDE_DELAY 后重新评估：仍离开底部则浮现按钮
 */
function onScroll() {
  if (isProgrammaticScroll) return
  userScrolledUp.value = false
  clearTimeout(scrollHideTimer)
  scrollHideTimer = setTimeout(() => {
    const el = messagesContainer.value
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    userScrolledUp.value = distanceFromBottom > SCROLL_THRESHOLD
  }, SCROLL_HIDE_DELAY)
}

/** 点击"回到底部"按钮 */
function handleScrollToBottomClick() {
  scrollToBottom(true)
}

// 消息变化时自动滚动：
// - 用户正在底部 → 自动跟上（流式输出时每次 token 追加都触发）
// - 用户已上滚 → 保持位置，不打断阅读
// - forceScrollOnce（发送/切换会话）→ 强制滚回
watch(
  () => props.messages,
  () => nextTick(() => {
    if (forceScrollOnce) {
      forceScrollOnce = false
      scrollToBottom(false)
    } else if (!userScrolledUp.value) {
      scrollToBottom(false)
    }
  }),
  { deep: true }
)

// 切换会话时强制滚到底部（加载历史消息后定位到最新）
watch(
  () => props.conversationId,
  () => {
    forceScrollOnce = true
    userScrolledUp.value = false
  }
)

// 挂载后绑定 scroll 监听，并在首次渲染时滚到底部（加载历史消息后定位）
onMounted(() => {
  if (messagesContainer.value) {
    messagesContainer.value.addEventListener('scroll', onScroll, { passive: true })
  }
  if (props.messages.length > 0) {
    scrollToBottom(false)
  }
})

// 卸载时清理监听与定时器，防止内存泄漏
onBeforeUnmount(() => {
  clearTimeout(scrollHideTimer)
  if (messagesContainer.value) {
    messagesContainer.value.removeEventListener('scroll', onScroll)
  }
})

// 回退预填文本：prefillText.ts 变化时填入输入框并聚焦
//（用 ts 时间戳而非直接比较对象，确保相同文本内容也能触发）
watch(
  () => props.prefillText?.ts || 0,
  (ts) => {
    if (ts && props.prefillText?.text) {
      inputText.value = props.prefillText.text
      nextTick(() => {
        if (inputRef.value) {
          inputRef.value.focus()
          autoResize()
        }
      })
    }
  }
)

/** 发送消息（非空且非加载中时） */
function handleSend() {
  const text = inputText.value.trim()
  if (!text || props.isLoading) return
  // 发送消息时强制滚到底部（即使用户正在上滚阅读历史）
  forceScrollOnce = true
  userScrolledUp.value = false
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

<style scoped>
/* ---- 回到底部浮动按钮 ---- */
/* 固定在消息容器底部居中，用户上滚时淡入显示，点击平滑滚回最新。
   使用主题变量保持与整体暖色风格一致。 */
.scroll-to-bottom-btn {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%) translateY(12px);
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
  /* 默认隐藏：透明 + 不可点击 + 向下偏移 */
  opacity: 0;
  pointer-events: none;
  transition:
    opacity var(--transition-normal, 0.25s ease),
    transform var(--transition-normal, 0.25s ease),
    background var(--transition-fast, 0.15s ease),
    color var(--transition-fast, 0.15s ease);
  z-index: 10;
}

.scroll-to-bottom-btn.visible {
  opacity: 1;
  pointer-events: auto;
  transform: translateX(-50%) translateY(0);
}

.scroll-to-bottom-btn:hover {
  background: var(--accent-dim, rgba(232, 187, 94, 0.10));
  color: var(--accent, #e8bb5e);
  border-color: var(--accent-glow, rgba(232, 187, 94, 0.20));
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4), 0 0 12px var(--accent-glow, rgba(232, 187, 94, 0.15));
}

.scroll-to-bottom-btn:active {
  transform: translateX(-50%) scale(0.92);
}
</style>
