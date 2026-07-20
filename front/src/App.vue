<!--
  App.vue — 应用根组件

  职责：
    1. 管理全局状态（会话列表、消息、工具选择、加载状态）
    2. 协调侧边栏（ConversationList）与聊天区域（ChatView）
    3. 处理 SSE 流式响应的解析与消息构建

  消息数据结构（内部统一格式）：
    用户消息:  { role: 'user', content: '...' }
    助手消息:  { role: 'assistant', segments: [
      { type: 'text', content: '...' },                        — 文本片段
      { type: 'tool_call', tool, args, observation }            — 工具调用片段
        observation=null 表示工具正在执行中（显示加载动画）
        observation=string 表示工具已返回结果
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
      @rename="handleRenameConversation"
      @pin="handlePinConversation"
      @unpin="handleUnpinConversation"
    />

    <!-- 主区域：聊天视图（含消息列表 + 输入框 + 工具选择器） -->
    <div class="main-area">
      <ChatView
        :messages="messages"
        :is-loading="isLoading"
        :tools="availableTools"
        :selected-tools="selectedTools"
        :conversation-id="currentConversationId"
        :prefill-text="prefillText"
        :pending-actions="pendingActions"
        @send="sendMessage"
        @toggle-tool="toggleTool"
        @reload-tools="handleReloadTools"
        @clear-history="handleClearHistory"
        @delete-message="handleDeleteMessage"
        @rewind="handleRewind"
        @approval-submit="handleApprovalSubmit"
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
  reloadTools,
  deleteConversation,
  clearConversationMessages,
  batchDeleteMessages,
  renameConversation,
  pinConversation,
  unpinConversation,
  chatStream,
  submitDecisions,
} from './api/index.js'
import { registerToolDisplayNames } from './utils/index.js'

// ============================================
// 响应式状态
// ============================================
const conversations = ref([])          // 会话列表
const currentConversationId = ref(null) // 当前选中的会话 ID
const messages = ref([])               // 当前会话的消息列表
const availableTools = ref([])         // 后端可用工具列表
const selectedTools = ref([])          // 用户选中的工具名称列表
const isLoading = ref(false)           // 是否正在等待 AI 响应
const pendingActions = ref(null)       // HITL 待审批的工具调用列表（null 表示无审批）
let abortController = null             // 用于取消进行中的请求

/**
 * 审批状态缓存：按会话 ID 保存/恢复待审批状态
 *
 * 当用户在一个会话中触发 HITL 审批后切换到另一个会话时，
 * 将当前 pendingActions 保存到 Map 中；切换回来时自动恢复。
 *
 * key: conversation_id
 * value: { actions: Array } — 待审批的工具调用列表
 */
const pendingApprovalStore = new Map()

/**
 * 处理单个 SSE 事件并更新助手消息的 segments 数组
 *
 * 被 sendMessage（新消息）和 handleApprovalSubmit（审批恢复）共用，
 * 避免两处重复相同的事件解析逻辑。
 *
 * @param {Object} assistantMsg - reactive 助手消息对象（含 segments 数组）
 * @param {string} eventType - SSE 事件类型
 * @param {Object} data - 事件数据
 * @returns {'approval_required'|null} 若事件为 approval_required 则返回该字符串，否则 null
 */
function processSseEvent(assistantMsg, eventType, data) {
  const segs = assistantMsg.segments
  switch (eventType) {
    case 'start':
      currentConversationId.value = data.conversation_id
      break

    case 'token': {
      const last = segs[segs.length - 1]
      if (last && last.type === 'text') {
        last.content += data.content
      } else {
        segs.push({ type: 'text', content: data.content })
      }
      break
    }

    case 'thinking': {
      // 先找是否有 approval_required 阶段预插入的 pending 段（同工具名 + observation=null）
      let existing = null
      for (let k = segs.length - 1; k >= 0; k--) {
        if (segs[k].type === 'tool_call' && segs[k].tool === data.tool && segs[k].observation == null) {
          existing = segs[k]
          break
        }
      }
      if (existing) {
        // 用后端 resume 返回的真实 call_id / args 更新 pending 段
        existing.call_id = data.call_id || ''
        if (data.args) existing.args = data.args
      } else {
        segs.push({
          type: 'tool_call',
          tool: data.tool,
          call_id: data.call_id || '',
          args: data.args,
          observation: data.observation ?? null,
        })
      }
      break
    }

    case 'tool_result': {
      let matched = false
      if (data.call_id) {
        for (let k = segs.length - 1; k >= 0; k--) {
          if (segs[k].type === 'tool_call' && segs[k].call_id === data.call_id) {
            segs[k].observation = data.observation
            matched = true
            break
          }
        }
      }
      if (!matched) {
        for (let k = segs.length - 1; k >= 0; k--) {
          if (segs[k].type === 'tool_call' && segs[k].observation == null) {
            segs[k].observation = data.observation
            break
          }
        }
      }
      break
    }

    case 'done': {
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

    case 'approval_required': {
      // 在助手消息中插入等待审批的工具调用段（observation=null 显示 loading）
      if (data.actions && data.actions.length > 0) {
        for (const action of data.actions) {
          // 避免重复插入（resume 后可能再次触发 approval_required）
          const dup = segs.find(s => s.type === 'tool_call' && s.tool === action.name && s.observation == null)
          if (!dup) {
            segs.push({
              type: 'tool_call',
              tool: action.name,
              call_id: '',
              args: action.args || {},
              observation: null,
            })
          }
        }
      }
      return 'approval_required'
    }
  }
  return null
}

/**
 * 创建流式消息管理器
 *
 * 持有"当前正在填充的助手消息"引用。当会新增内容的事件（token / thinking / error）
 * 到达时，若当前消息的最后一段是**已完成**的工具调用（observation != null），
 * 则自动新建一条 reactive 助手消息并 push 进 messages.value，后续内容写入新消息。
 *
 * 目的：使流式渲染与历史加载渲染保持一致。
 *   后端将"工具结果后的总结"存储为独立的 AIMessage，processHistoryMessages 会
 *   把它转成一条独立的助手消息（自带头像）；若流式时把总结追加进含工具调用的
 *   同一条消息，就会导致"流式无头像、刷新后有头像"的显示不一致。
 *
 * @param {Object} firstMsg - 初始的 reactive 助手消息（已 push 进 messages.value）
 * @returns {{ process: Function, current: Object }}
 *   process(eventType, data) — 处理 SSE 事件，必要时自动拆分出新消息
 *   current — 当前正在填充的消息（catch 中追加错误文本时使用）
 */
function createStreamManager(firstMsg) {
  const state = { current: firstMsg }

  /** 若当前消息最后一段是已完成的工具调用，则新建消息承载后续内容 */
  function ensureFreshMessage(eventType) {
    // 只有会新增内容的事件才需要判断是否拆分
    if (eventType !== 'token' && eventType !== 'thinking' && eventType !== 'error') return
    const segs = state.current.segments
    const last = segs[segs.length - 1]
    // 最后一段是已完成的工具调用 → 后续内容应独立成新消息（与历史渲染一致）
    if (last && last.type === 'tool_call' && last.observation != null) {
      const next = reactive({
        id: 'temp_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7),
        role: 'assistant',
        segments: [],
      })
      messages.value.push(next)
      state.current = next
    }
  }

  return {
    get current() {
      return state.current
    },
    process(eventType, data) {
      ensureFreshMessage(eventType)
      return processSseEvent(state.current, eventType, data)
    },
  }
}

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
      // 将后端返回的中文显示名称注册到全局响应式映射表
      registerToolDisplayNames(tools)
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
  // ---- 保存当前会话的审批状态（如果有未提交的审批） ----
  if (pendingActions.value && currentConversationId.value) {
    pendingApprovalStore.set(currentConversationId.value, {
      actions: pendingActions.value,
    })
  }

  currentConversationId.value = convId

  try {
    const data = await fetchHistory(convId)
    messages.value = processHistoryMessages(data.messages || [])

    // ---- 恢复审批状态 ----
    // 优先使用内存缓存（切换会话时保存的）；
    // 若缓存中没有，则检查后端返回的 pending_actions（页面刷新后从 checkpointer 恢复）
    const cached = pendingApprovalStore.get(convId)
    if (cached) {
      pendingActions.value = cached.actions
    } else if (data.pending_actions && data.pending_actions.length > 0) {
      pendingActions.value = data.pending_actions
    } else {
      pendingActions.value = null
    }

    // ---- 恢复审批等待中的工具调用 loading 段 ----
    // processHistoryMessages 给未执行工具生成的 observation=''（空字符串），
    // 需要替换为 observation=null 才能触发 loading 动画
    if (pendingActions.value && pendingActions.value.length > 0) {
      const pendingNames = new Set(pendingActions.value.map(a => a.name))
      // 找到最后一条助手消息
      for (let k = messages.value.length - 1; k >= 0; k--) {
        const m = messages.value[k]
        if (m.role === 'assistant' && m.segments) {
          for (const seg of m.segments) {
            if (seg.type === 'tool_call' && pendingNames.has(seg.tool) && seg.observation === '') {
              seg.observation = null  // 触发 loading 动画
            }
          }
          break
        }
      }
    }
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
      result.push({ id: msg.id, role: 'user', content: msg.content })
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

      result.push({ id: msg.id, role: 'assistant', segments })
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
  // 保存当前会话的审批状态
  if (pendingActions.value && currentConversationId.value) {
    pendingApprovalStore.set(currentConversationId.value, {
      actions: pendingActions.value,
    })
  }
  currentConversationId.value = null
  messages.value = []
  // 新对话没有待审批
  pendingActions.value = null
}

/** 删除指定会话并刷新列表 */
async function handleDeleteConversation(convId) {
  try {
    await deleteConversation(convId)
    // 清除该会话的审批状态缓存
    pendingApprovalStore.delete(convId)
    await loadConversations()
    if (currentConversationId.value === convId) {
      pendingActions.value = null
      newChat()
    }
  } catch (e) {
    console.error('删除会话失败:', e)
  }
}

/** 重命名指定会话并刷新列表 */
async function handleRenameConversation(convId, newTitle) {
  try {
    await renameConversation(convId, newTitle)
    await loadConversations()
  } catch (e) {
    console.error('重命名会话失败:', e)
  }
}

/** 顶置指定会话并刷新列表 */
async function handlePinConversation(convId) {
  try {
    await pinConversation(convId)
    await loadConversations()
  } catch (e) {
    console.error('顶置会话失败:', e)
  }
}

/** 取消顶置指定会话并刷新列表 */
async function handleUnpinConversation(convId) {
  try {
    await unpinConversation(convId)
    await loadConversations()
  } catch (e) {
    console.error('取消顶置会话失败:', e)
  }
}

/** 清空当前会话的消息上下文（保留会话条目） */
async function handleClearHistory() {
  const convId = currentConversationId.value
  if (!convId) return
  try {
    await clearConversationMessages(convId)
    messages.value = []
    // 对话上下文被清除，审批状态也不再有意义
    pendingActions.value = null
    pendingApprovalStore.delete(convId)
  } catch (e) {
    console.error('清空对话上下文失败:', e)
  }
}

/** 删除指定消息（及其之后所有消息） */
async function handleDeleteMessage(messageId) {
  const convId = currentConversationId.value
  if (!convId || !messageId) return
  try {
    const result = await batchDeleteMessages(convId, [messageId])
    console.log(`已删除 ${result.deleted_count} 条消息`)
    // 重新加载历史以获取最新的消息列表（含正确的消息 ID）
    if (convId === currentConversationId.value) {
      const data = await fetchHistory(convId)
      messages.value = processHistoryMessages(data.messages || [])
      pendingActions.value = data.pending_actions || null
    }
  } catch (e) {
    console.error('删除消息失败:', e)
  }
}

/** 回退：将消息内容填入输入框，并删除该消息及之后所有消息 */
async function handleRewind({ id, content }) {
  const convId = currentConversationId.value
  if (!convId || !id) return
  try {
    await batchDeleteMessages(convId, [id])
    // 重新加载历史
    if (convId === currentConversationId.value) {
      const data = await fetchHistory(convId)
      messages.value = processHistoryMessages(data.messages || [])
      pendingActions.value = data.pending_actions || null
    }
    // 回填消息内容到输入框（用对象 + 时间戳确保相同文本也能触发 watch）
    prefillText.value = { text: content, ts: Date.now() }
  } catch (e) {
    console.error('回退失败:', e)
  }
}

// 回退时的预填文本（用对象包装，确保相同文本内容也能触发 watch）
const prefillText = ref({ text: '', ts: 0 })

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

/**
 * 热重载 MCP 工具并刷新列表
 *
 * 流程：
 *   1. 调用后端 POST /api/tools/reload 重新加载 MCP 工具
 *   2. 重新获取工具列表并更新前端状态
 *   3. 自动清理已不存在的工具选中状态（由 loadTools 内部处理）
 */
async function handleReloadTools() {
  try {
    await reloadTools()
    await loadTools()
  } catch (e) {
    console.error('重载 MCP 工具失败:', e)
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

  // 如果当前有未处理的审批面板，清除它（后端会自动拒绝挂起的工具调用）
  if (pendingActions.value && currentConversationId.value) {
    pendingApprovalStore.delete(currentConversationId.value)
  }
  pendingActions.value = null

  // 添加用户消息（临时 ID：流式过程中消息还没有 LangChain 分配的正式 ID）
  messages.value.push({ id: 'temp_' + Date.now(), role: 'user', content: text })

  isLoading.value = true
  abortController = new AbortController()

  // 创建空的助手消息（reactive 包装确保 segments 的深层变更能被 Vue 追踪）
  const assistantMsg = reactive({
    id: 'temp_' + (Date.now() + 1),
    role: 'assistant',
    segments: [],
  })
  messages.value.push(assistantMsg)

  // 流式消息管理器：工具调用完成后，后续内容自动拆分到新消息（与历史渲染一致，各有头像）
  const stream = createStreamManager(assistantMsg)

  try {
    await chatStream(
      {
        message: text,
        conversation_id: currentConversationId.value,
        selected_tools: selectedTools.value,
      },
      (eventType, data) => {
        const result = stream.process(eventType, data)
        if (result === 'approval_required') {
          // 工具调用需要审批 → 设置待审批列表，显示审批面板
          pendingActions.value = data.actions
        }
      },
      abortController.signal,
    )
  } catch (e) {
    // AbortError 是用户主动取消，不算错误
    if (e.name !== 'AbortError') {
      console.error('聊天请求失败:', e)
      const segs = stream.current.segments
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
    // 流式正常结束（非 HITL 中断）时，重新加载历史用真实 ID 替换临时 ID
    // HITL 中断时跳过：此时工具尚未执行，重载历史会产生 observation='' 的假完成段，
    // 与 resume 恢复后 thinking 事件产生的段重复，导致两个工具调用框
    if (!pendingActions.value) {
      const convId = currentConversationId.value
      if (convId) {
        try {
          const data = await fetchHistory(convId)
          messages.value = processHistoryMessages(data.messages || [])
        } catch {
          // 历史加载失败不影响主流程
        }
      }
    }
  }
}

/**
 * 处理审批面板提交的决策
 *
 * 用户在 ApprovalPanel 中对所有待审批工具做出决策后触发。
 * 将决策提交给后端 POST /api/chat/decide，恢复 Agent 执行并继续接收 SSE 流。
 * 恢复后若再次触发 HITL 中断，会重新弹出审批面板（支持多轮审批）。
 *
 * @param {Array} decisions - 决策数组，与 pendingActions 一一对应
 *   每项格式：{ type: 'approve' } | { type: 'edit', edited_action: {...} } | { type: 'reject', message: '...' }
 */
async function handleApprovalSubmit(decisions) {
  const convId = currentConversationId.value
  if (!convId) return

  // 隐藏审批面板，并从缓存中移除
  pendingActions.value = null
  pendingApprovalStore.delete(convId)

  isLoading.value = true
  abortController = new AbortController()

  // 复用最后一条助手消息作为 resume 流式目标：
  // approval_required 阶段已把待执行工具段（observation=null，loading 中）预插入该消息，
  // resume 的 thinking 事件会按工具名匹配并更新它的 call_id，随后 tool_result 按 call_id
  // 填充结果、结束 loading——整个过程只有一张工具卡片。
  // 若另建空消息，thinking/tool_result 会写进新消息，旧的 pending 段被遗弃而永远 loading，
  // 界面上就会"结果已出、loading 还在转"。
  // reactive() 幂等：消息已是响应式则原样返回；历史重载后的普通对象则包成代理，
  // 保证 segments 深层变更可被 Vue 追踪。
  let assistantMsg = null
  for (let k = messages.value.length - 1; k >= 0; k--) {
    if (messages.value[k].role === 'assistant') {
      assistantMsg = reactive(messages.value[k])
      messages.value[k] = assistantMsg
      break
    }
  }
  // 兜底：没有助手消息（审批必然跟在助手消息之后，理论上不会走到这里）则新建
  if (!assistantMsg) {
    assistantMsg = reactive({
      id: 'temp_resume_' + Date.now(),
      role: 'assistant',
      segments: [],
    })
    messages.value.push(assistantMsg)
  }

  // 流式消息管理器：工具调用完成后，后续总结内容自动拆分到新消息（与历史渲染一致，各有头像）
  const stream = createStreamManager(assistantMsg)

  try {
    await submitDecisions(
      { conversation_id: convId, decisions },
      (eventType, data) => {
        const result = stream.process(eventType, data)
        if (result === 'approval_required') {
          // Agent 恢复执行后再次触发了需要审批的工具调用（多轮审批）
          pendingActions.value = data.actions
        }
      },
      abortController.signal,
    )
  } catch (e) {
    if (e.name !== 'AbortError') {
      console.error('审批提交失败:', e)
      const segs = stream.current.segments
      segs.push({ type: 'text', content: '\n[网络错误] 审批提交失败，请检查后端服务。' })
    }
  } finally {
    isLoading.value = false
    abortController = null
    await loadConversations()
    // 流式正常结束（非 HITL 中断）时，重新加载历史用真实 ID 替换临时 ID
    // HITL 中断时跳过：此时工具尚未执行，重载历史会产生 observation='' 的假完成段，
    // 与 resume 恢复后 thinking 事件产生的段重复，导致两个工具调用框
    if (!pendingActions.value) {
      const convId = currentConversationId.value
      if (convId) {
        try {
          const data = await fetchHistory(convId)
          messages.value = processHistoryMessages(data.messages || [])
        } catch {
          // 历史加载失败不影响主流程
        }
      }
    }
  }
}
</script>
