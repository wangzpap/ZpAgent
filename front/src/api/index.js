/**
 * API 封装模块
 * 封装与后端的所有 HTTP 交互，包括普通请求和 SSE 流式请求
 */

const BASE = '/api'

// ============================================
// 普通 REST 请求
// ============================================

/** 获取所有会话列表 */
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
 * 使用 fetch + ReadableStream 实现 POST 方式的 SSE：
 *   1. POST 请求体包含消息、会话 ID、选中的工具
 *   2. 响应是 text/event-stream 格式
 *   3. 逐行解析 SSE 事件并回调 onEvent
 *
 * @param {Object} payload - { message, conversation_id, selected_tools }
 * @param {Function} onEvent - 事件回调 (eventType, data) => void
 * @param {AbortSignal} signal - 用于取消请求的信号
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

    // 按双换行分割完整的 SSE 事件
    const events = buffer.split('\n\n')
    buffer = events.pop() // 保留不完整的事件

    for (const eventStr of events) {
      if (!eventStr.trim()) continue

      let eventType = ''
      let data = ''

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
