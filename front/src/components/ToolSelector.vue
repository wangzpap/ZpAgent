<!--
  ToolSelector.vue — 下拉多选工具选择器（分组版）

  放置在输入框底部区域，点击按钮展开浮动面板进行工具多选。
  使用 Teleport 将下拉面板渲染到 body，避免被父组件 overflow 裁切。

  功能：
    - 内置工具（inner_tool）和 MCP 工具分层展示
    - MCP 工具按 server_name 分组，每组支持全选/取消全选
    - 单个工具可独立选择/取消
    - 全局全选/取消全选
    - 刷新 MCP 工具（reload 事件，调用后端热重载接口）
-->
<template>
  <div class="tool-selector" ref="selectorRef">
    <!-- 触发按钮 -->
    <button
      class="tool-trigger"
      :class="{ open: isOpen }"
      @click="toggleOpen"
      ref="triggerRef"
    >
      <svg class="icon-svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
      </svg>
      <span>工具</span>
      <span class="count-badge">{{ selected.length }}</span>
      <svg class="arrow-svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </button>

    <!-- 下拉面板（Teleport 到 body 避免层叠上下文问题） -->
    <Teleport to="body">
      <template v-if="isOpen">
        <div class="tool-overlay" @click="closeAll" />
        <div class="tool-dropdown" :style="dropdownStyle" @click.stop>
          <!-- 头部：标题 + 刷新 / 全选/取消全选 -->
          <div class="tool-dropdown-header">
            <span>已启用工具</span>
            <div class="header-actions">
              <button
                class="refresh-btn"
                :class="{ spinning: isReloading }"
                @click="handleReload"
                :disabled="isReloading"
                title="刷新 MCP 工具"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="23 4 23 10 17 10"/>
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                </svg>
              </button>
              <button v-if="tools.length > 0" class="toggle-all" @click="toggleAll">
                {{ allSelected ? '取消全选' : '全选' }}
              </button>
            </div>
          </div>

          <!-- 空状态 -->
          <div v-if="tools.length === 0" class="tool-empty">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            暂无可用工具，请检查后端服务
          </div>

          <!-- 工具列表（分组展示，可滚动） -->
          <div class="tool-list-scroll" :style="{ maxHeight: listMaxHeight + 'px' }">

            <!-- 内置工具分组 -->
            <div v-if="builtinTools.length > 0" class="tool-group">
              <div class="group-header">
                <span class="group-label">内置工具</span>
                <span class="group-count">{{ builtinTools.length }}</span>
              </div>
              <div
                v-for="tool in builtinTools"
                :key="tool.name"
                class="tool-option"
                :class="{ checked: selected.includes(tool.name) }"
                @click="$emit('toggle', tool.name)"
              >
                <div class="checkbox">
                  <svg v-if="selected.includes(tool.name)" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                </div>
                <div class="tool-label">
                  <div class="tool-name">{{ tool.display_name || tool.name }}</div>
                  <div class="tool-desc">{{ shortDesc(tool.description) }}</div>
                </div>
                <button class="more-btn" @click.stop="showDetail(tool, $event)" title="查看详情">
                  <span></span><span></span><span></span>
                </button>
              </div>
            </div>

            <!-- MCP 工具按 server_name 分组 -->
            <div
              v-for="group in mcpGroups"
              :key="group.serverName"
              class="tool-group"
            >
              <div class="group-header">
                <div class="group-header-left" @click="toggleGroup(group.serverName)">
                  <div class="group-checkbox" :class="{
                    checked: group.allSelected,
                    indeterminate: group.someSelected && !group.allSelected
                  }">
                    <!-- 全选状态：对勾 -->
                    <svg v-if="group.allSelected" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                    <!-- 半选状态：横线 -->
                    <svg v-else-if="group.someSelected" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                      <line x1="5" y1="12" x2="19" y2="12"/>
                    </svg>
                  </div>
                  <span class="group-label">{{ group.serverName }}</span>
                </div>
                <span class="group-count">{{ group.tools.length }}</span>
              </div>
              <div
                v-for="tool in group.tools"
                :key="tool.name"
                class="tool-option tool-option-nested"
                :class="{ checked: selected.includes(tool.name) }"
                @click="$emit('toggle', tool.name)"
              >
                <div class="checkbox">
                  <svg v-if="selected.includes(tool.name)" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                </div>
                <div class="tool-label">
                  <div class="tool-name">{{ tool.display_name || tool.name }}</div>
                  <div class="tool-desc">{{ shortDesc(tool.description) }}</div>
                </div>
                <button class="more-btn" @click.stop="showDetail(tool, $event)" title="查看详情">
                  <span></span><span></span><span></span>
                </button>
              </div>
            </div>

          </div>
        </div>

        <!-- 工具详情浮动窗口（独立于下拉面板） -->
        <div v-if="detailTool" ref="popoverRef" class="tool-detail-popover" :style="detailStyle" @click.stop>
          <div class="detail-popover-header">
            <span class="detail-popover-title">{{ detailTool.display_name || detailTool.name }}</span>
            <button class="detail-popover-close" @click="detailTool = null">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
          <div class="detail-content">
            <div class="detail-row"><span class="detail-key">名称</span>{{ detailTool.name }}</div>
            <div class="detail-row detail-row-block">
              <span class="detail-key">描述</span>
              <span class="detail-val">{{ detailTool.description || '—' }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-key">类型</span>{{ detailTool.tool_type === 'inner_tool' ? '内置工具' : 'MCP 工具' }}
            </div>
            <div v-if="detailTool.tool_type === 'mcp' && detailTool.server_name" class="detail-row">
              <span class="detail-key">来源</span>{{ detailTool.server_name }}
            </div>
            <div class="detail-row">
              <span class="detail-key">审批</span>{{ detailTool.requires_approval ? '需要审批' : '自动执行' }}
            </div>
            <div class="detail-row detail-row-block">
              <span class="detail-key">参数</span>
              <pre class="detail-params">{{ formatParams(detailTool.parameters) }}</pre>
            </div>
          </div>
        </div>

      </template>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  tools:    { type: Array, default: () => [] },  // 可用工具列表
  selected: { type: Array, default: () => [] },  // 已选工具名称列表
})

const emit = defineEmits(['toggle', 'reload'])

const isOpen = ref(false)
const isReloading = ref(false)
const triggerRef = ref(null)
const dropdownStyle = ref({})
const listMaxHeight = ref(300)
const detailTool = ref(null)   // 当前展开详情的工具对象（完整 tool 数据）
const detailStyle = ref({})    // 详情浮动窗口的定位样式
const popoverRef = ref(null)   // 浮动窗口 DOM 引用，用于测量实际高度

// ---- 工具分组 ----

/** 内置工具（tool_type === 'inner_tool'） */
const builtinTools = computed(
  () => props.tools.filter((t) => t.tool_type === 'inner_tool')
)

/** MCP 工具按 server_name 分组 */
const mcpGroups = computed(() => {
  const mcpTools = props.tools.filter((t) => t.tool_type === 'mcp')
  // 按 server_name 聚合
  const map = new Map()
  for (const tool of mcpTools) {
    const server = tool.server_name || 'unknown'
    if (!map.has(server)) map.set(server, [])
    map.get(server).push(tool)
  }
  // 转为数组，每组附带选中状态
  return Array.from(map.entries()).map(([serverName, tools]) => {
    const selectedCount = tools.filter((t) => props.selected.includes(t.name)).length
    return {
      serverName,
      tools,
      selectedCount,
      allSelected: selectedCount === tools.length,
      someSelected: selectedCount > 0,
    }
  })
})

// 是否全部选中
const allSelected = computed(
  () => props.tools.length > 0 && props.selected.length === props.tools.length
)

// ---- 交互逻辑 ----

/** 关闭下拉面板及详情窗口 */
function closeAll() {
  isOpen.value = false
  detailTool.value = null
}

/** 切换下拉面板的显示/隐藏 */
async function toggleOpen() {
  if (isOpen.value) {
    closeAll()
  } else {
    isOpen.value = true
    await nextTick()
    calcPosition()
  }
}
/** 切换工具详情浮动窗口 */
async function showDetail(tool, event) {
  // 再次点击同一个工具则关闭
  if (detailTool.value && detailTool.value.name === tool.name) {
    detailTool.value = null
    return
  }

  detailTool.value = tool

  const btn = event.currentTarget
  const btnRect = btn.getBoundingClientRect()
  const popoverWidth = 340
  const gap = 8

  // 水平方向：优先在按钮右侧展开，空间不足则左侧
  let left
  const rightSpace = window.innerWidth - btnRect.right - gap
  if (rightSpace >= popoverWidth) {
    left = btnRect.right + gap
  } else {
    left = Math.max(gap, btnRect.left - popoverWidth - gap)
  }

  // 先以按钮顶部对齐、先渲染，再测量实际高度后修正垂直位置
  detailStyle.value = {
    position: 'fixed',
    left: `${left}px`,
    top: `${btnRect.top}px`,
  }

  await nextTick()

  // 测量渲染后的实际高度，确保不超出视口底部
  if (popoverRef.value) {
    const actualHeight = popoverRef.value.offsetHeight
    const viewportBottom = window.innerHeight - gap
    let top = btnRect.top

    if (top + actualHeight > viewportBottom) {
      // 方案一：从按钮底部向上展开
      top = btnRect.bottom - actualHeight
    }
    // 如果向上也不够空间（内容比视口还高），则贴顶显示
    if (top < gap) {
      top = gap
    }

    detailStyle.value = {
      position: 'fixed',
      left: `${left}px`,
      top: `${top}px`,
    }
  }
}

function calcPosition() {
  if (!triggerRef.value) return
  const rect = triggerRef.value.getBoundingClientRect()
  const bottomOffset = window.innerHeight - rect.top + 8
  dropdownStyle.value = {
    position: 'fixed',
    left: `${rect.left}px`,
    bottom: `${bottomOffset}px`,
  }
  listMaxHeight.value = Math.max(120, window.innerHeight - bottomOffset - 48 - 16)
}

function handleResize() {
  if (isOpen.value) calcPosition()
}

onMounted(() => window.addEventListener('resize', handleResize))
onBeforeUnmount(() => window.removeEventListener('resize', handleResize))

async function handleReload() {
  if (isReloading.value) return
  isReloading.value = true
  try {
    await emit('reload')
  } finally {
    await new Promise((r) => setTimeout(r, 600))
    isReloading.value = false
  }
}

/** 全选 / 取消全选 */
function toggleAll() {
  if (allSelected.value) {
    props.tools.forEach((t) => {
      if (props.selected.includes(t.name)) emit('toggle', t.name)
    })
  } else {
    props.tools.forEach((t) => {
      if (!props.selected.includes(t.name)) emit('toggle', t.name)
    })
  }
}

/** 组级全选 / 取消全选 */
function toggleGroup(serverName) {
  const group = mcpGroups.value.find((g) => g.serverName === serverName)
  if (!group) return
  if (group.allSelected) {
    // 组内全部取消
    group.tools.forEach((t) => {
      if (props.selected.includes(t.name)) emit('toggle', t.name)
    })
  } else {
    // 组内未选的选中
    group.tools.forEach((t) => {
      if (!props.selected.includes(t.name)) emit('toggle', t.name)
    })
  }
}

/** 截断描述文本 */
function shortDesc(desc) {
  if (!desc) return ''
  const first = desc.split('\n')[0].trim()
  return first.length > 30 ? first.slice(0, 30) + '...' : first
}

/** 格式化参数 Schema 为可读字符串 */
function formatParams(schema) {
  if (!schema) return '无参数'
  try {
    const props = schema.properties || {}
    const required = schema.required || []
    const keys = Object.keys(props)
    if (keys.length === 0) return '无参数'
    return keys.map((k) => {
      const p = props[k]
      const type = p.type || 'any'
      const req = required.includes(k) ? ' (必填)' : ''
      const desc = p.description ? ` — ${p.description}` : ''
      return `${k}: ${type}${req}${desc}`
    }).join('\n')
  } catch {
    return JSON.stringify(schema, null, 2)
  }
}
</script>

<style scoped>
.icon-svg {
  transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.tool-trigger.open .icon-svg {
  transform: rotate(45deg);
}

.arrow-svg {
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.tool-trigger.open .arrow-svg {
  transform: rotate(180deg);
}

.refresh-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: var(--radius-xxs);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.refresh-btn:hover:not(:disabled) {
  background: var(--accent-dim);
  color: var(--accent);
}

.refresh-btn:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.refresh-btn.spinning svg {
  animation: spin 0.75s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
</style>

<style>
/* 工具选择器（下拉多选，分组版）
   非 scoped — 下拉面板通过 Teleport 渲染到 body，scoped 样式无法穿透 */

.tool-selector {
  position: relative;
}

.tool-trigger {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 13px;
  background: rgba(255,255,255,0.025);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xs);
  cursor: pointer;
  font-size: 12px;
  font-family: var(--font-ui);
  color: var(--text-secondary);
  transition: all var(--transition-fast);
  user-select: none;
}

.tool-trigger:hover {
  border-color: var(--accent);
  color: var(--text-primary);
  background: var(--accent-dim);
}

.tool-trigger.open {
  border-color: var(--accent);
  background: var(--accent-dim);
  color: var(--text-primary);
}

.tool-trigger .count-badge {
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-hover) 100%);
  color: var(--bg-base);
  font-size: 10px;
  font-weight: 700;
  padding: 0 7px;
  border-radius: 9px;
  min-width: 19px;
  text-align: center;
  line-height: 19px;
  box-shadow: 0 1px 5px var(--accent-glow);
}

/* 点击外部关闭的遮罩 */
.tool-overlay {
  position: fixed;
  inset: 0;
  z-index: 99;
}

/* 下拉面板 */
.tool-dropdown {
  min-width: 320px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-float);
  z-index: 200;
  overflow: hidden;
  animation: dropdown-in 0.25s var(--ease-out);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

@keyframes dropdown-in {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.tool-dropdown-header {
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tool-dropdown-header .toggle-all {
  font-size: 11px;
  color: var(--accent);
  cursor: pointer;
  background: none;
  border: none;
  font-family: var(--font-ui);
  font-weight: 500;
  padding: 4px 10px;
  border-radius: var(--radius-xxs);
  transition: all var(--transition-fast);
}

.tool-dropdown-header .toggle-all:hover {
  background: var(--accent-dim);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 工具列表滚动区域 */
.tool-list-scroll {
  overflow-y: auto;
  overscroll-behavior: contain;
}

.tool-list-scroll::-webkit-scrollbar { width: 4px; }
.tool-list-scroll::-webkit-scrollbar-track { background: transparent; }
.tool-list-scroll::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.06);
  border-radius: 4px;
}
.tool-list-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(255,255,255,0.18);
}

.tool-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 24px 18px;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
}

/* ---- 分组样式 ---- */
.tool-group + .tool-group {
  border-top: 1px solid var(--border-light);
}

.group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 18px 6px;
  user-select: none;
}

.group-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  flex: 1;
  min-width: 0;
}

.group-checkbox {
  width: 16px;
  height: 16px;
  border: 1.5px solid var(--border-light);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all var(--transition-fast);
  color: transparent;
}

.group-checkbox.checked {
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-hover) 100%);
  border-color: var(--accent);
  color: var(--bg-base);
  box-shadow: 0 2px 8px var(--accent-glow);
}

.group-checkbox.indeterminate {
  border-color: var(--accent);
  background: var(--accent-dim);
  color: var(--accent);
}

.group-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-count {
  font-size: 10px;
  color: var(--text-muted);
  background: rgba(255,255,255,0.04);
  padding: 1px 7px;
  border-radius: 8px;
  flex-shrink: 0;
}

/* ---- 工具选项 ---- */
.tool-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 18px;
  cursor: pointer;
  transition: all var(--transition-fast);
  border-bottom: 1px solid var(--border);
}

/* MCP 分组内的工具选项：增加左侧缩进，与分组复选框视觉对齐 */
.tool-option-nested {
  padding-left: 42px;
}

.tool-option:last-child {
  border-bottom: none;
}

.tool-group:last-child .tool-option:last-child {
  border-bottom: none;
}

.tool-option:hover {
  background: var(--bg-hover);
}

.tool-option .checkbox {
  width: 18px;
  height: 18px;
  border: 1.5px solid var(--border-light);
  border-radius: var(--radius-xxs);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all var(--transition-fast);
  font-size: 10px;
  color: transparent;
}

.tool-option.checked .checkbox {
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-hover) 100%);
  border-color: var(--accent);
  color: var(--bg-base);
  box-shadow: 0 2px 8px var(--accent-glow);
}

.tool-option .tool-label {
  flex: 1;
  min-width: 0;
}

.tool-option .tool-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.tool-option .tool-desc {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ---- 三点更多按钮 ---- */
.more-btn {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 6px 4px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: var(--radius-xxs);
  opacity: 0;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.tool-option:hover .more-btn {
  opacity: 1;
}

.more-btn:hover {
  background: rgba(255,255,255,0.08);
}

.more-btn span {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--text-muted);
  transition: background 0.2s ease;
}

.more-btn:hover span {
  background: var(--accent);
}

/* ---- 工具详情浮动窗口 ---- */
.tool-detail-popover {
  width: 340px;
  max-height: 420px;
  overflow-y: auto;
  background: var(--bg-elevated);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-float), 0 0 0 1px rgba(255,255,255,0.03);
  z-index: 210;
  animation: popover-in 0.2s var(--ease-out);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.tool-detail-popover::-webkit-scrollbar { width: 4px; }
.tool-detail-popover::-webkit-scrollbar-track { background: transparent; }
.tool-detail-popover::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.06);
  border-radius: 4px;
}
.tool-detail-popover::-webkit-scrollbar-thumb:hover {
  background: rgba(255,255,255,0.18);
}

@keyframes popover-in {
  from {
    opacity: 0;
    transform: translateX(-6px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateX(0) scale(1);
  }
}

.detail-popover-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}

.detail-popover-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.detail-popover-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: var(--radius-xxs);
  flex-shrink: 0;
  transition: all 0.15s ease;
}

.detail-popover-close:hover {
  background: rgba(255,255,255,0.08);
  color: var(--text-primary);
}

.detail-content {
  padding: 12px 18px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-size: 12px;
  color: var(--text-primary);
  line-height: 1.5;
}

.detail-row-block {
  flex-direction: column;
  gap: 4px;
}

.detail-key {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  flex-shrink: 0;
  min-width: 42px;
}

.detail-val {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-params {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
  padding: 8px 12px;
  background: rgba(0,0,0,0.15);
  border-radius: var(--radius-xxs);
  border: 1px solid var(--border);
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-x: auto;
}
</style>
