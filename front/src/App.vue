<!--
  App.vue — 应用根组件
  管理全局状态，协调侧边栏与聊天区域
  工具选择器已移至 ChatView 输入区底部
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

    <!-- 主区域：聊天视图（含工具选择器） -->
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
const conversations = ref([])
const currentConversationId = ref(null)
const messages = ref([])
const availableTools = ref([])
const selectedTools = ref([])
const isLoading = ref(false)
let abortController = null

// ============================================
// 初始化
// ============================================
onMounted(async () => {
  await loadConversations()
  await loadTools()
})

async function loadConversations() {
  try {
    conversations.value = await fetchConversations()
  } catch (e) {
    console.error('加载会话列表失败:', e)
  }
}

async function loadTools() {
  const MAX_RETRIES = 3
  for (let i = 0; i < MAX_RETRIES; i++) {
    try {
      const tools = await fetchTools()
      availableTools.value = tools
      const validNames = new Set(tools.map((t) => t.name))
      // 过滤掉不存在的工具名（如后端工具变更后残留的旧名称）
      selectedTools.value = selectedTools.value.filter((n) =>
        validNames.has(n)
      )
      // 如果过滤后为空但工具列表非空，默认全选
      if (selectedTools.value.length === 0 && tools.length > 0) {
        selectedTools.value = tools.map((t) => t.name)
      }
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
 * 将后端存储的原始消息序列转换为前端展示格式：
 *  - user → 原样保留
 *  - assistant（含 tool_calls）→ 按时间线构建 segments：
 *      text 片段（content）+ tool_call 片段（工具调用及观察结果）
 *  - assistant（纯文本）→ 单个 text 片段
 *  - tool → 跳过（已被 assistant 的 tool_call 消费）
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
      // 跳过独立的 tool 消息（已被上面的 tool_call 构建消费）
      i++
    }
  }

  return result
}

function newChat() {
  currentConversationId.value = null
  messages.value = []
}

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
async function sendMessage(text) {
  if (isLoading.value || !text.trim()) return

  messages.value.push({ role: 'user', content: text })

  isLoading.value = true
  abortController = new AbortController()

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
            // 工具调用：新建一个 tool_call 片段，严格按时间线插入
            segs.push({
              type: 'tool_call',
              tool: data.tool,
              args: data.args,
              observation: data.observation,
            })
            break
          }
          case 'done': {
            // 清除最后一个 text 片段的首尾空白
            for (let k = segs.length - 1; k >= 0; k--) {
              if (segs[k].type === 'text') {
                segs[k].content = segs[k].content.trim()
                break
              }
            }
            break
          }
          case 'error': {
            const lastE = segs[segs.length - 1]
            const errText = `\n[错误] ${data.content}`
            if (lastE && lastE.type === 'text') {
              lastE.content += errText
            } else {
              segs.push({ type: 'text', content: errText })
            }
            break
          }
        }
      },
      abortController.signal
    )
  } catch (e) {
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
