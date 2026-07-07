<!--
  ToolSelector.vue — 下拉多选工具选择器

  放置在输入框底部区域，点击按钮展开浮动面板进行工具多选。
  使用 Teleport 将下拉面板渲染到 body，避免被父组件 overflow 裁切。

  功能：
    - 多选/取消选择工具（toggle 事件）
    - 全选/取消全选
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
      <!-- 已选数量徽标 -->
      <span class="count-badge">{{ selected.length }}</span>
      <svg class="arrow-svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </button>

    <!-- 下拉面板（Teleport 到 body 避免层叠上下文问题） -->
    <Teleport to="body">
      <template v-if="isOpen">
        <!-- 点击遮罩关闭 -->
        <div class="tool-overlay" @click="isOpen = false" />
        <!-- 下拉内容 -->
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

          <!-- 工具列表（多选，可滚动） -->
          <div class="tool-list-scroll" :style="{ maxHeight: listMaxHeight + 'px' }">
            <div
              v-for="tool in tools"
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

// 事件：toggle（切换工具选中）、reload（刷新 MCP 工具列表）
const emit = defineEmits(['toggle', 'reload'])

const isOpen = ref(false)
const isReloading = ref(false)   // 刷新按钮的加载状态（控制旋转动画）
const triggerRef = ref(null)
const dropdownStyle = ref({})
const listMaxHeight = ref(300)   // 工具列表最大高度（动态计算）

// 是否全部选中
const allSelected = computed(
  () => props.tools.length > 0 && props.selected.length === props.tools.length
)

/** 切换下拉面板的显示/隐藏 */
async function toggleOpen() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    await nextTick()
    calcPosition()
  }
}

/** 根据触发按钮位置计算下拉面板的固定坐标和列表最大高度 */
function calcPosition() {
  if (!triggerRef.value) return
  const rect = triggerRef.value.getBoundingClientRect()
  const bottomOffset = window.innerHeight - rect.top + 8
  dropdownStyle.value = {
    position: 'fixed',
    left: `${rect.left}px`,
    bottom: `${bottomOffset}px`,
  }
  // 下拉面板从按钮上方展开，可用高度 = 视口高度 - 底部偏移 - 头部高度(~48px) - 安全边距(16px)
  listMaxHeight.value = Math.max(120, window.innerHeight - bottomOffset - 48 - 16)
}

/** 窗口 resize 时重新计算位置 */
function handleResize() {
  if (isOpen.value) calcPosition()
}

onMounted(() => window.addEventListener('resize', handleResize))
onBeforeUnmount(() => window.removeEventListener('resize', handleResize))

/**
 * 刷新 MCP 工具
 *
 * 触发 reload 事件通知父组件调用后端重载接口，
 * 同时显示旋转动画给用户操作反馈（至少 0.6 秒）。
 */
async function handleReload() {
  if (isReloading.value) return
  isReloading.value = true
  try {
    await emit('reload')
  } finally {
    // 至少显示 0.6 秒旋转动画，确保用户能看到加载反馈
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

/** 截断描述文本（最多 30 字符） */
function shortDesc(desc) {
  if (!desc) return ''
  const first = desc.split('\n')[0].trim()
  return first.length > 30 ? first.slice(0, 30) + '...' : first
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

/* 刷新按钮 */
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
/* 工具选择器（下拉多选）
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

.tool-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 18px;
  cursor: pointer;
  transition: all var(--transition-fast);
  border-bottom: 1px solid var(--border);
}

.tool-option:last-child {
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
</style>
