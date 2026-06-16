<!--
  App.vue — 应用根组件

  职责：
    1. 管理全局状态（会话列表、消息、工具选择、加载状态）
    2. 协调侧边栏（ConversationList）与聊天区域（ChatView）
    3. 处理 SSE 流式响应的解析与消息构建

  消息数据结构（内部统一格式）：
    用户消息:  { role: 'user', content: '...' }
    助手消息:  { role: 'assistant', segments: [
      { type: 'text', content: '...' },           — 文本片段
      { type: 'tool_call', tool, args, observation } — 工具调用片段
    ]}
-->
<template>
  <div class="app-container">
    <!-- 侧边栏：会话列表 -->
    <ConversationList
      :conversations="conversations"
      :current-id="currentConversationId"
      @select="selectConversation"
      @new-chat="newChat"
      @delete="handleDeleteConversation"
    />

    <!-- 主区域：聊天视图（含消息列表 + 输入框 + 工具选择器） -->
    <div class="main-area">
      <ChatView
        :messages="messages"
        :is-loading="isLoading"
        :tools="availableTools"
        :selected-tools="selectedTools"
        @send="sendMessage"
        @toggle-tool="toggleTool"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import ConversationList from './components/ConversationList.vue'
import ChatView from './views/ChatView.vue'
import {
  fetchConversations,
  fetchHistory,
  fetchTools,
  deleteConversation,
  chatStream,
} from './api/index.js'

// ============================================
// 响应式状态
// ============================================
const conversations = ref([])          // 会话列表
const currentConversationId = ref(null) // 当前选中的会话 ID
const messages = ref([])               // 当前会话的消息列表
const availableTools = ref([])         // 后端可用工具列表
const selectedTools = ref([])          // 用户选中的工具名称列表
const isLoading = ref(false)           // 是否正在等待 AI 响应
let abortController = null             // 用于取消进行中的请求

// ============================================
// 初始化：加载会话列表和工具列表
// ============================================
onMounted(async () => {
  await loadConversations()
  await loadTools()
})

/** 加载会话列表 */
async function loadConversations() {
  try {
    conversations.value = await fetchConversations()
  } catch (e) {
    console.error('加载会话列表失败:', e)
  }
}

/**
 * 加载工具列表（含重试机制）
 * 后端启动可能比前端慢，因此最多重试 3 次，间隔 2 秒
 */
async function loadTools() {
  const MAX_RETRIES = 3
  for (let i = 0; i < MAX_RETRIES; i++) {
    try {
      const tools = await fetchTools()
      availableTools.value = tools
      // 过滤掉不存在的工具名（后端工具变更后可能残留旧名称）
      const validNames = new Set(tools.map((t) => t.name))
      selectedTools.value = selectedTools.value.filter((n) => validNames.has(n))
      return
    } catch (e) {
      console.error(`加载工具列表失败 (第 ${i + 1} 次):`, e)
      if (i < MAX_RETRIES - 1) {
        await new Promise((r) => setTimeout(r, 2000))
      }
    }
  }
}

// ============================================
// 会话操作
// ============================================

/** 选择并加载指定会话的历史消息 */
async function selectConversation(convId) {
  currentConversationId.value = convId
  try {
    const data = await fetchHistory(convId)
    messages.value = processHistoryMessages(data.messages || [])
  } catch (e) {
    console.error('加载会话历史失败:', e)
  }
}

/**
 * 将后端存储的原始消息序列转换为前端展示格式
 *
 * 转换规则：
 *   - user 消息 → { role: 'user', content }
 *   - assistant（含 tool_calls）→ { role: 'assistant', segments: [text, tool_call, ...] }
 *     其中 tool_call 的 observation 从后续的 tool 消息中匹配获取
 *   - tool 消息 → 跳过（已被 assistant 的 tool_call 消费）
 */
function processHistoryMessages(raw) {
  const result = []
  let i = 0

  while (i < raw.length) {
    const msg = raw[i]

    if (msg.role === 'user') {
      result.push({ role: 'user', content: msg.content })
      i++
    } else if (msg.role === 'assistant') {
      const segments = []

      // 文本内容作为 text 片段
      if (msg.content) {
        segments.push({ type: 'text', content: msg.content })
      }

      // 如果有 tool_calls，收集对应的 tool 结果，构建 tool_call 片段
      if (msg.tool_calls && msg.tool_calls.length > 0) {
        for (const tc of msg.tool_calls) {
          let observation = ''
          // 向后查找匹配的 tool 消息
          for (let j = i + 1; j < raw.length; j++) {
            if (raw[j].role === 'tool' && raw[j].tool_call_id === tc.id) {
              observation = raw[j].content
              break
            }
          }
          segments.push({
            type: 'tool_call',
            tool: tc.name,
            args: tc.args,
            observation,
          })
        }
      }

      result.push({ role: 'assistant', segments })
      i++
    } else {
      // 跳过独立的 tool 消息
      i++
    }
  }

  return result
}

/** 新建对话（清空当前选中状态） */
function newChat() {
  currentConversationId.value = null
  messages.value = []
}

/** 删除指定会话并刷新列表 */
async function handleDeleteConversation(convId) {
  try {
    await deleteConversation(convId)
    await loadConversations()
    if (currentConversationId.value === convId) newChat()
  } catch (e) {
    console.error('删除会话失败:', e)
  }
}

// ============================================
// 工具选择
// ============================================

/** 切换工具选中状态 */
function toggleTool(toolName) {
  const idx = selectedTools.value.indexOf(toolName)
  if (idx >= 0) {
    selectedTools.value.splice(idx, 1)
  } else {
    selectedTools.value.push(toolName)
  }
}

// ============================================
// 发送消息 & 流式接收
// ============================================

/**
 * 发送用户消息并通过 SSE 流式接收 AI 响应
 *
 * 流程：
 *   1. 添加用户消息到消息列表
 *   2. 创建空的助手消息（reactive segments 数组）
 *   3. 调用 chatStream，根据事件类型逐步填充 segments
 *   4. 完成后刷新会话列表
 */
async function sendMessage(text) {
  if (isLoading.value || !text.trim()) return

  // 添加用户消息
  messages.value.push({ role: 'user', content: text })

  isLoading.value = true
  abortController = new AbortController()

  // 创建空的助手消息（reactive 包装确保 segments 的深层变更能被 Vue 追踪）
  const assistantMsg = reactive({
    role: 'assistant',
    segments: [],
  })
  messages.value.push(assistantMsg)

  try {
    await chatStream(
      {
        message: text,
        conversation_id: currentConversationId.value,
        selected_tools: selectedTools.value,
      },
      (eventType, data) => {
        const segs = assistantMsg.segments
        switch (eventType) {
          case 'start':
            // 获取后端分配的会话 ID
            currentConversationId.value = data.conversation_id
            break

          case 'token': {
            // 流式文本：追加到最后一个 text 片段，或新建一个
            const last = segs[segs.length - 1]
            if (last && last.type === 'text') {
              last.content += data.content
            } else {
              segs.push({ type: 'text', content: data.content })
            }
            break
          }

          case 'thinking': {
            // 工具调用：新建 tool_call 片段，严格按时间线插入
            segs.push({
              type: 'tool_call',
              tool: data.tool,
              args: data.args,
              observation: data.observation,
            })
            break
          }

          case 'done': {
            // 清理最后一个 text 片段的首尾空白
            for (let k = segs.length - 1; k >= 0; k--) {
              if (segs[k].type === 'text') {
                segs[k].content = segs[k].content.trim()
                break
              }
            }
            break
          }

          case 'error': {
            const errText = `\n[错误] ${data.content}`
            const lastE = segs[segs.length - 1]
            if (lastE && lastE.type === 'text') {
              lastE.content += errText
            } else {
              segs.push({ type: 'text', content: errText })
            }
            break
          }
        }
      },
      abortController.signal,
    )
  } catch (e) {
    // AbortError 是用户主动取消，不算错误
    if (e.name !== 'AbortError') {
      console.error('聊天请求失败:', e)
      const segs = assistantMsg.segments
      const last = segs[segs.length - 1]
      const errText = '\n[网络错误] 请求失败，请检查后端服务是否运行。'
      if (last && last.type === 'text') {
        last.content += errText
      } else {
        segs.push({ type: 'text', content: errText })
      }
    }
  } finally {
    isLoading.value = false
    abortController = null
    await loadConversations()
  }
}
</script>
