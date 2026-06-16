/**
 * API 封装模块
 *
 * 封装与后端的所有 HTTP 交互，包括：
 *   - 普通 REST 请求（会话列表、消息历史、删除会话、工具列表）
 *   - SSE 流式聊天请求（POST + text/event-stream）
 *
 * 所有请求通过 Vite 代理 /api → http://localhost:8000/api 转发到后端。
 */

const BASE = '/api'

// ============================================
// 普通 REST 请求
// ============================================

/** 获取所有会话列表（按更新时间倒序） */
export async function fetchConversations() {
  const res = await fetch(`${BASE}/conversations`)
  return res.json()
}

/** 获取指定会话的消息历史 */
export async function fetchHistory(conversationId) {
  const res = await fetch(`${BASE}/messages/${conversationId}`)
  return res.json()
}

/** 删除指定会话 */
export async function deleteConversation(conversationId) {
  const res = await fetch(`${BASE}/conversations/${conversationId}`, {
    method: 'DELETE',
  })
  return res.json()
}

/** 获取所有可用工具列表 */
export async function fetchTools() {
  const res = await fetch(`${BASE}/tools`)
  return res.json()
}

// ============================================
// SSE 流式聊天请求
// ============================================

/**
 * 发送聊天消息并通过 SSE 接收流式响应
 *
 * 实现原理：
 *   1. 使用 fetch POST 发送请求（body 包含消息、会话ID、选定工具）
 *   2. 响应为 text/event-stream 格式，通过 ReadableStream 逐块读取
 *   3. 按 SSE 协议解析（event: xxx \n data: yyy \n\n），回调 onEvent
 *
 * SSE 事件类型：
 *   - start:    对话开始（data.conversation_id）
 *   - token:    流式文本 token（data.content）
 *   - thinking: 工具调用步骤（data.tool / args / observation）
 *   - done:     对话结束（data.conversation_id / reply）
 *   - error:    错误信息（data.content）
 *
 * @param {Object} payload - { message, conversation_id, selected_tools }
 * @param {Function} onEvent - 事件回调 (eventType: string, data: object) => void
 * @param {AbortSignal} signal - 用于取消请求的信号（来自 AbortController）
 */
export async function chatStream(payload, onEvent, signal) {
  const response = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // 按双换行分割完整的 SSE 事件，保留最后一个不完整的事件
    const events = buffer.split('\n\n')
    buffer = events.pop()

    for (const eventStr of events) {
      if (!eventStr.trim()) continue

      let eventType = ''
      let data = ''

      // 解析 event: 和 data: 行
      for (const line of eventStr.split('\n')) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          data = line.slice(6)
        }
      }

      if (eventType && data) {
        try {
          onEvent(eventType, JSON.parse(data))
        } catch (e) {
          console.error('SSE parse error:', e, eventStr)
        }
      }
    }
  }
}
