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
          <!-- 工具调用片段：可折叠卡片（默认折叠，头部=步骤徽标+工具名+状态+耗时+箭头） -->
          <div
            v-else-if="seg.type === 'tool_call'"
            class="tool-card"
            :class="{
              running: seg.observation == null,
              failed: seg.observation != null && seg.ok === false,
              expanded: isExpanded(idx),
            }"
          >
            <!-- 卡片头部（整行可点击切换展开） -->
            <button class="tool-card-header" @click="toggleStep(idx)">
              <span class="tool-step-badge">{{ stepNumbers[idx] }}</span>
              <span class="tool-card-name">{{ toolDisplayName(seg.tool) }}</span>
              <span class="tool-card-status">
                <!-- 执行中：observation 尚未到达 -->
                <template v-if="seg.observation == null">
                  <span class="status-dot running"></span>
                  <span class="status-text running">执行中</span>
                </template>
                <!-- 失败：后端下发 ok=false（ToolMessage.status === 'error'） -->
                <template v-else-if="seg.ok === false">
                  <span class="status-dot failed"></span>
                  <span class="status-text failed">失败</span>
                </template>
                <!-- 完成：成功，或历史消息无 ok 字段时的中性态 -->
                <template v-else>
                  <span class="status-dot done"></span>
                  <span class="status-text done">完成</span>
                </template>
              </span>
              <span v-if="seg.duration_ms != null" class="tool-card-duration">{{ formatDuration(seg.duration_ms) }}</span>
              <svg class="tool-card-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </button>

            <!-- 折叠主体：grid-template-rows 0fr→1fr 实现平滑高度动画 -->
            <div class="tool-card-body-wrap">
              <div class="tool-card-body">
                <div class="tool-card-body-inner">
                  <!-- 参数区：格式化 JSON + 语法高亮 -->
                  <div v-if="seg.args && Object.keys(seg.args).length" class="tool-section">
                    <div class="tool-section-label">参数</div>
                    <pre class="tool-json" v-html="highlightJson(seg.args)"></pre>
                  </div>
                  <!-- 结果区：尝试按 JSON 高亮，否则转义后原样展示 -->
                  <div v-if="seg.observation != null" class="tool-section">
                    <div class="tool-section-label">结果</div>
                    <pre class="tool-result" v-html="renderObservation(seg.observation)"></pre>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
        </div>
      </template>

      <!-- 操作按钮区（hover 气泡时显示，仅助手消息渲染，避免用户消息下出现空 div 占位） -->
      <div v-if="message.role === 'assistant' && assistantText" class="copy-btn-area">
        <!-- 一键复制按钮 -->
        <button class="copy-btn" :class="{ copied }" @click.stop="copyContent" :title="copied ? '已复制' : '复制回复内容'">
          <template v-if="!copied">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
            <span>复制</span>
          </template>
          <template v-else>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            <span>已复制</span>
          </template>
        </button>
      </div>

      <!-- 用户消息正文 -->
      <div
        v-if="message.role === 'user' && message.content"
        class="message-bubble"
        :class="message.role"
      >
        {{ message.content }}
      </div>

      <!-- 用户消息删除按钮（气泡外右下角，hover 消息行时显示） -->
      <div
        v-if="message.role === 'user' && message.id && !isTempId(message.id)"
        class="user-delete-row"
      >
        <!-- 回退按钮 -->
        <div class="user-delete-area" :class="{ 'has-popover': showRewindPopover }">
          <button
            class="user-action-btn"
            :class="{ active: showRewindPopover }"
            @click.stop="toggleRewindPopover"
            title="回退到此消息之前"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="1 4 1 10 7 10"/>
              <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
            </svg>
            <span>回退</span>
          </button>

          <div v-if="showRewindPopover" class="delete-popover" @click.stop>
            <div class="popover-warn">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="1 4 1 10 7 10"/>
                <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
              </svg>
              <span>将把该消息重新填入输入框，并删除该消息及其之后的所有消息，此操作不可恢复</span>
            </div>
            <div class="popover-actions">
              <button class="popover-btn confirm" @click.stop="doRewind">确认回退</button>
              <button class="popover-btn cancel" @click.stop="cancelRewindPopover">取消</button>
            </div>
          </div>
        </div>

        <!-- 删除按钮 -->
        <div class="user-delete-area" :class="{ 'has-popover': showDeletePopover }">
          <button
            class="user-action-btn"
            :class="{ active: showDeletePopover }"
            @click.stop="toggleDeletePopover"
            title="删除此轮对话"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            </svg>
            <span>删除</span>
          </button>

          <div v-if="showDeletePopover" class="delete-popover" @click.stop>
            <div class="popover-warn">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
              <span>将删除该消息及其之后的所有消息，且无法恢复</span>
            </div>
            <div class="popover-actions">
              <button class="popover-btn confirm" @click.stop="doDelete">确认删除</button>
              <button class="popover-btn cancel" @click.stop="cancelDeletePopover">取消</button>
            </div>
          </div>
        </div>
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
import { ref, reactive, computed } from 'vue'
import { marked } from 'marked'
import { toolDisplayName } from '../utils/index.js'

// 配置 marked：GFM 模式 + 换行转 <br>
marked.setOptions({ breaks: true, gfm: true })

const props = defineProps({
  message:    { type: Object, required: true },
  isLatest:   { type: Boolean, default: false },
})

const emit = defineEmits(['delete', 'rewind'])

/** 提取助手消息中的纯文本内容（用于复制） */
const assistantText = computed(() => {
  if (!props.message.segments) return ''
  return props.message.segments
    .filter(s => s.type === 'text' && s.content)
    .map(s => s.content)
    .join('\n')
})

// ---- 工具调用卡片：步骤编号 / 展开状态 / JSON 高亮 ----

/**
 * 步骤编号映射：segments 数组下标 idx -> 卡片显示的步骤序号。
 *
 * 编号优先采用后端下发的 ReAct 迭代轮次（seg.step）：同一轮 LLM 推理内并行调用的
 * 多个工具会共享同一 step（它们本就属于同一步），这是符合语义的；历史消息无 step
 * 字段时，按工具调用出现顺序回退为 1、2、3…，保证编号始终连续可读。
 *
 * 以 idx 作为 map 键是安全的：单条消息的 segments 只会追加、不会重排，idx 与工具
 * 卡片一一对应且稳定。
 */
const stepNumbers = computed(() => {
  const map = {}
  let ordinal = 0
  ;(props.message.segments || []).forEach((seg, idx) => {
    if (seg.type !== 'tool_call') return
    ordinal++
    map[idx] = seg.step != null ? seg.step : ordinal
  })
  return map
})

/** 各工具卡片的展开状态（idx -> bool），默认折叠 */
const expandedMap = reactive({})

function isExpanded(idx) {
  return !!expandedMap[idx]
}

function toggleStep(idx) {
  expandedMap[idx] = !expandedMap[idx]
}

/** HTML 转义，防止工具参数/结果中的内容被当作标签注入（XSS 防护） */
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

/**
 * 轻量 JSON 语法高亮（无第三方依赖）。
 *
 * 处理顺序很关键：先 JSON.stringify 序列化 → 再 escapeHtml 转义 → 最后用正则
 * 包裹配色 span。因为正则作用于"已转义"的纯文本，此时文档中尚无任何 <span> 标签，
 * 引号/尖括号等也已被替换为实体，所以既不会破坏 JSON 的引号结构，也天然规避了
 * 把工具返回值当 HTML 注入的 XSS 风险。
 *
 * 正则分支（按优先级从左到右，先匹配者胜出）：
 *   1. ("...")(\s*:)?  字符串；若其后紧跟冒号则为键名(json-key)，否则为字符串值(json-str)
 *   2. \b(true|false)\b 布尔(json-bool)
 *   3. \b(null)\b       空值(json-null)
 *   4. 数字（含小数/科学计数法）(json-num)
 * 字符串分支排在最前，可确保字符串内部的数字/单词被整体当作字符串，不会被误判。
 */
function highlightJson(value) {
  let raw
  try {
    raw = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  } catch {
    return escapeHtml(String(value))
  }
  if (raw == null) return ''
  const escaped = escapeHtml(raw)
  return escaped.replace(
    /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false)\b|\b(null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
    (match, str, colon, bool, nul, num) => {
      if (str) {
        // 带冒号后缀的是键名，否则是字符串值
        return colon
          ? `<span class="json-key">${str}</span>${colon}`
          : `<span class="json-str">${str}</span>`
      }
      if (bool) return `<span class="json-bool">${bool}</span>`
      if (nul) return `<span class="json-null">${nul}</span>`
      if (num) return `<span class="json-num">${num}</span>`
      return match
    },
  )
}

/**
 * 渲染工具执行结果：若结果形似 JSON（以 { 或 [ 开头）则尝试解析并高亮，
 * 否则按纯文本转义后原样展示（保留换行）。
 */
function renderObservation(obs) {
  const text = String(obs ?? '')
  const trimmed = text.trim()
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try {
      return highlightJson(JSON.parse(trimmed))
    } catch {
      // 解析失败则退回纯文本
    }
  }
  return escapeHtml(text)
}

/** 耗时格式化：< 1000ms 显示毫秒，否则保留两位小数显示秒 */
function formatDuration(ms) {
  if (ms == null) return ''
  return ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(2)}s`
}

const copied = ref(false)

/** 一键复制助手回复内容到剪贴板 */
async function copyContent() {
  try {
    await navigator.clipboard.writeText(assistantText.value)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    // 降级：静默失败
  }
}

const showDeletePopover = ref(false)

/** 判断是否为前端生成的临时 ID（以 temp_ 开头） */
function isTempId(id) {
  return id && id.startsWith('temp_')
}

/** 切换删除确认弹窗（打开 delete 时关闭 rewind） */
function toggleDeletePopover() {
  showRewindPopover.value = false
  showDeletePopover.value = !showDeletePopover.value
}

/** 取消删除 */
function cancelDeletePopover() {
  showDeletePopover.value = false
}

/** 确认删除 */
function doDelete() {
  showDeletePopover.value = false
  emit('delete', props.message.id)
}

// ---- 回退功能（rewind） ----
const showRewindPopover = ref(false)

/** 切换回退确认弹窗（打开 rewind 时关闭 delete） */
function toggleRewindPopover() {
  showDeletePopover.value = false
  showRewindPopover.value = !showRewindPopover.value
}

/** 取消回退 */
function cancelRewindPopover() {
  showRewindPopover.value = false
}

/** 确认回退：将消息内容回填到输入框，并删除该消息及之后所有消息 */
function doRewind() {
  showRewindPopover.value = false
  emit('rewind', { id: props.message.id, content: props.message.content })
}

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

/* ---- 工具调用卡片（可折叠） ---- */
.tool-card {
  background: var(--bg-thinking);
  border: 1px solid rgba(232, 187, 94, 0.14);
  border-radius: var(--radius-xs);
  overflow: hidden;
  transition: border-color var(--transition-normal), box-shadow var(--transition-normal);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
}

.tool-card:hover {
  border-color: rgba(232, 187, 94, 0.28);
}

/* 执行中：边框微亮，提示进行中 */
.tool-card.running {
  border-color: rgba(232, 187, 94, 0.25);
}

/* 失败：红色边框，提示工具执行出错 */
.tool-card.failed {
  border-color: rgba(239, 107, 107, 0.40);
}

.tool-card.failed:hover {
  border-color: rgba(239, 107, 107, 0.60);
}

/* 展开态：加强阴影，突出内容 */
.tool-card.expanded {
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.18);
}

/* 头部：整行按钮，flex 布局承载徽标/名称/状态/耗时/箭头 */
.tool-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 11px 14px;
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  font-family: var(--font-ui);
  transition: background var(--transition-fast);
}

.tool-card-header:hover {
  background: var(--bg-hover);
}

/* 步骤编号圆形徽标 */
.tool-step-badge {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 5px;
  border-radius: 50%;
  background: var(--accent-dim);
  border: 1px solid var(--border-accent);
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
}

.tool-card-name {
  color: var(--text-asst);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 状态区：靠右对齐 */
.tool-card-status {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

/* 执行中：琥珀色脉冲呼吸 */
.status-dot.running {
  background: var(--accent);
  animation: tool-status-pulse 1.2s ease-in-out infinite;
}

.status-dot.done {
  background: var(--success);
}

/* 失败：红色常亮 */
.status-dot.failed {
  background: var(--danger);
}

.status-text {
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.4px;
}

.status-text.running {
  color: var(--accent);
}

.status-text.done {
  color: var(--success);
}

.status-text.failed {
  color: var(--danger);
}

@keyframes tool-status-pulse {
  0%, 100% { opacity: 0.35; transform: scale(0.8); }
  50%      { opacity: 1;    transform: scale(1.15); }
}

/* 耗时：等宽字体，弱化显示 */
.tool-card-duration {
  flex-shrink: 0;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 10.5px;
  opacity: 0.85;
}

/* 展开箭头：默认朝下，折叠态旋转 -90° */
.tool-card-chevron {
  flex-shrink: 0;
  color: var(--text-secondary);
  transition: transform var(--transition-fast);
  transform: rotate(-90deg);
}

.tool-card.expanded .tool-card-chevron {
  transform: rotate(0deg);
}

/* 折叠主体：grid-template-rows 0fr→1fr 平滑展开，无需预知高度 */
.tool-card-body-wrap {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.28s var(--ease-out);
}

.tool-card.expanded .tool-card-body-wrap {
  grid-template-rows: 1fr;
}

.tool-card-body {
  overflow: hidden;
  min-height: 0;
}

.tool-card-body-inner {
  padding: 2px 14px 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  border-top: 1px solid var(--border);
}

/* 分区标签（参数 / 结果） */
.tool-section-label {
  font-size: 9.5px;
  font-weight: 650;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--accent);
  margin: 10px 0 6px;
  opacity: 0.9;
}

/* 参数 / 结果代码块 */
.tool-json,
.tool-result {
  margin: 0;
  padding: 12px 14px;
  background: rgba(0, 0, 0, 0.22);
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--text-asst);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* JSON 语法高亮配色。
   必须用 :deep() 穿透：高亮 span 由 v-html 注入，不会携带 Vue scoped 的 data-v-*
   属性，普通 scoped 选择器（如 .tool-json .json-key）会被编译加上属性约束而失效，
   只有 :deep() 能命中这些动态注入的子元素。 */
.tool-json :deep(.json-key),
.tool-result :deep(.json-key) {
  color: var(--accent);
}

.tool-json :deep(.json-str),
.tool-result :deep(.json-str) {
  color: #9ece8f;
}

.tool-json :deep(.json-num),
.tool-result :deep(.json-num) {
  color: #7fb0d6;
}

.tool-json :deep(.json-bool),
.tool-result :deep(.json-bool) {
  color: #c792d6;
}

.tool-json :deep(.json-null),
.tool-result :deep(.json-null) {
  color: #8a8aa0;
  font-style: italic;
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

/* ---- 一键复制按钮（hover 气泡时显示） ---- */
.copy-btn-area {
  margin-top: 6px;
  display: flex;
  align-items: center;
}

.copy-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-xxs);
  color: var(--text-muted);
  font-size: 11px;
  font-family: var(--font-ui);
  cursor: pointer;
  transition: all 0.2s var(--ease-out);
  opacity: 0;
  transform: translateY(2px);
}

/* hover 消息行时显示复制按钮 */
.message-wrapper:hover .copy-btn {
  opacity: 1;
  transform: translateY(0);
}

.copy-btn:hover {
  color: var(--accent);
  border-color: var(--border-accent);
  background: var(--accent-dim);
}

/* 复制成功态 */
.copy-btn.copied {
  color: var(--success);
  border-color: rgba(74, 222, 128, 0.30);
  background: rgba(74, 222, 128, 0.10);
  opacity: 1;
}

/* ---- 用户消息删除按钮（气泡外右下角） ---- */
.user-delete-row {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  margin-top: 4px;
  position: relative;
}

.user-delete-area {
  position: relative;
}

.user-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-xxs);
  color: var(--text-muted);
  font-size: 11px;
  font-family: var(--font-ui);
  cursor: pointer;
  transition: all 0.2s var(--ease-out);
  opacity: 0;
  transform: translateY(2px);
}

/* hover 消息行时显示操作按钮 */
.message-wrapper:hover .user-action-btn {
  opacity: 1;
  transform: translateY(0);
}

.user-action-btn:hover,
.user-action-btn.active {
  color: var(--danger);
  border-color: rgba(239, 68, 68, 0.30);
  background: rgba(239, 68, 68, 0.10);
}

/* ---- 删除确认弹窗 ---- */
.delete-popover {
  position: absolute;
  right: 0;
  bottom: calc(100% + 8px);
  width: 280px;
  background: var(--bg-card);
  border: 1px solid var(--border-danger, rgba(239, 68, 68, 0.30));
  border-radius: var(--radius-xs);
  padding: 14px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.40);
  z-index: 20;
  animation: popover-in 0.18s var(--ease-out);
}

@keyframes popover-in {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}

.popover-warn {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  font-size: 12.5px;
  color: var(--text-primary);
  line-height: 1.6;
  margin-bottom: 12px;
}

.popover-warn svg {
  flex-shrink: 0;
  color: var(--danger);
  margin-top: 1px;
}

.popover-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.popover-btn {
  padding: 5px 14px;
  border-radius: var(--radius-xxs);
  font-size: 12px;
  font-family: var(--font-ui);
  cursor: pointer;
  transition: all 0.15s;
  border: 1px solid transparent;
}

.popover-btn.confirm {
  background: var(--danger);
  color: #fff;
  border-color: var(--danger);
}

.popover-btn.confirm:hover {
  opacity: 0.85;
}

.popover-btn.cancel {
  background: transparent;
  color: var(--text-secondary);
  border-color: var(--border);
}

.popover-btn.cancel:hover {
  border-color: var(--text-muted);
  color: var(--text-primary);
}

</style>
