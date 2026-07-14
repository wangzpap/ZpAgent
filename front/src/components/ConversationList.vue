<!--
  ConversationList.vue — 侧边栏会话列表

  展示所有历史会话，支持：
    - 新建对话（emit new-chat）
    - 选择会话（emit select）
    - 三点菜单 → 重命名 / 删除（emit rename / delete）
-->
<template>
  <aside class="sidebar">
    <!-- 品牌标题 -->
    <div class="sidebar-header">
      <div class="brand-row">
        <h1>Zp<span>Agent</span></h1>
        <div class="status-dot" title="Online"></div>
      </div>
      <p>ReAct Intelligent Agent</p>
    </div>

    <!-- 新建对话按钮 -->
    <button class="new-chat-btn" @click="$emit('new-chat')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
        <line x1="12" y1="5" x2="12" y2="19"/>
        <line x1="5" y1="12" x2="19" y2="12"/>
      </svg>
      新建对话
    </button>

    <!-- 会话列表 -->
    <div class="conv-list">
      <div
        v-for="conv in conversations"
        :key="conv.id"
        class="conv-item"
        :class="{ active: conv.id === currentId, editing: editingId === conv.id, pinned: conv.pinned_at }"
        @click="editingId !== conv.id && $emit('select', conv.id)"
      >
        <svg class="conv-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <!-- 顶置标记（仅已顶置的会话显示） -->
        <svg v-if="conv.pinned_at" class="pin-badge" width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
          <path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2l-2-2z"/>
        </svg>
        <!-- 编辑模式：输入框 -->
        <div v-if="editingId === conv.id" class="rename-wrapper">
          <input
            class="rename-input"
            :value="editTitle"
            @input="editTitle = $event.target.value"
            @keydown.enter.prevent="confirmRename(conv.id)"
            @keydown.escape.prevent="cancelRename"
            @blur="confirmRename(conv.id)"
            @click.stop
            maxlength="12"
          />
          <span class="rename-counter">{{ editTitle.length }}/12</span>
        </div>
        <!-- 显示模式：标题文本 -->
        <span v-else class="title">{{ conv.title || '新对话' }}</span>
        <!-- 三点菜单按钮（hover 时显示，编辑模式下隐藏） -->
        <button
          v-if="editingId !== conv.id"
          class="more-btn"
          :class="{ open: menuOpenId === conv.id }"
          @click.stop="toggleMenu($event, conv.id)"
          title="更多操作"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <circle cx="12" cy="5" r="1.8"/>
            <circle cx="12" cy="12" r="1.8"/>
            <circle cx="12" cy="19" r="1.8"/>
          </svg>
        </button>
        <!-- 下拉菜单 -->
        <Teleport to="body">
          <div v-if="menuOpenId === conv.id" class="conv-menu-overlay" @click="closeMenu">
            <div class="conv-dropdown" :style="menuStyle" @click.stop>
              <button class="conv-dropdown-item" @click="handleRename(conv)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>
                </svg>
                重命名
              </button>
              <!-- 顶置 / 取消顶置 -->
              <button
                class="conv-dropdown-item"
                @click="handleTogglePin(conv)"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2l-2-2z"/>
                </svg>
                {{ conv.pinned_at ? '取消顶置' : '顶置' }}
              </button>
              <button class="conv-dropdown-item danger" @click="handleDelete(conv.id)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="3 6 5 6 21 6"/>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
                删除
              </button>
            </div>
          </div>
        </Teleport>
      </div>

      <!-- 空状态 -->
      <div v-if="conversations.length === 0" class="conv-empty">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.3">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <span>暂无对话记录</span>
      </div>
    </div>

    <!-- 底部信息 + 设置按钮 -->
    <div class="sidebar-footer">
      <span class="version-text">ZpAgent</span>
      <button class="settings-btn" @click="showSettings = true" title="系统设置">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
      </button>
    </div>

    <!-- 删除确认弹窗 -->
    <ConfirmDialog
      :visible="showDeleteConfirm"
      title="删除对话"
      :message="`确定要删除「${deleteTargetTitle}」吗？删除后无法恢复。`"
      confirm-text="删除"
      cancel-text="取消"
      :danger="true"
      @confirm="confirmDelete"
      @cancel="cancelDelete"
    />

    <!-- 系统设置弹窗 -->
    <SettingsDialog
      :visible="showSettings"
      @close="showSettings = false"
    />
  </aside>
</template>

<script setup>
import { ref, computed, reactive, nextTick } from 'vue'
import ConfirmDialog from './ConfirmDialog.vue'
import SettingsDialog from './SettingsDialog.vue'

const props = defineProps({
  conversations: { type: Array, default: () => [] },
  currentId:     { type: String, default: null },
})

const emit = defineEmits(['select', 'new-chat', 'delete', 'rename', 'pin', 'unpin'])

// ---- 设置弹窗状态 ----
const showSettings = ref(false)

// ---- 删除确认弹窗状态 ----
const showDeleteConfirm = ref(false)
const deleteTargetId = ref(null)

/** 待删除会话的标题（用于弹窗提示文案） */
const deleteTargetTitle = computed(() => {
  const conv = props.conversations.find((c) => c.id === deleteTargetId.value)
  return conv?.title || '新对话'
})

/** 点击删除按钮 → 弹出确认弹窗 */
function requestDelete(convId) {
  deleteTargetId.value = convId
  showDeleteConfirm.value = true
}

/** 确认删除 → 触发 delete 事件并关闭弹窗 */
function confirmDelete() {
  if (deleteTargetId.value) {
    emit('delete', deleteTargetId.value)
  }
  showDeleteConfirm.value = false
  deleteTargetId.value = null
}

/** 取消删除 */
function cancelDelete() {
  showDeleteConfirm.value = false
  deleteTargetId.value = null
}

// ---- 三点菜单状态 ----
const menuOpenId = ref(null)
const menuStyle = reactive({ top: '0px', left: '0px' })
let menuClosedAt = 0  // 关闭菜单的时间戳，防止 overlay 关闭后立即重新打开

/** 切换菜单开关 */
function toggleMenu(ev, convId) {
  // 防止 overlay 点击关闭菜单后，按钮点击事件又立即重新打开
  if (Date.now() - menuClosedAt < 200) return
  if (menuOpenId.value === convId) {
    closeMenu()
    return
  }
  // 计算菜单位置：基于按钮位置定位
  const btn = ev.currentTarget
  const rect = btn.getBoundingClientRect()
  menuStyle.top = rect.bottom + 4 + 'px'
  menuStyle.left = rect.right - 140 + 'px' // 菜单宽度约 140px，右对齐到按钮
  // 确保不超出视口左边
  if (parseFloat(menuStyle.left) < 8) {
    menuStyle.left = '8px'
  }
  menuOpenId.value = convId
}

/** 关闭菜单 */
function closeMenu() {
  menuOpenId.value = null
  menuClosedAt = Date.now()
}

// ---- 重命名状态 ----
const editingId = ref(null)
const editTitle = ref('')

/** 从菜单触发重命名 */
function handleRename(conv) {
  closeMenu()
  editingId.value = conv.id
  editTitle.value = conv.title || '新对话'
  nextTick(() => {
    const input = document.querySelector('.rename-input')
    if (input) {
      input.focus()
      input.select()
    }
  })
}

/** 确认重命名 */
function confirmRename(convId) {
  // 防止 Enter 触发后 blur 再次调用（input 已从 DOM 移除时会触发 blur）
  if (editingId.value !== convId) return
  const newTitle = editTitle.value.trim()
  if (newTitle && newTitle !== '') {
    emit('rename', convId, newTitle)
  }
  editingId.value = null
  editTitle.value = ''
}

/** 取消重命名 */
function cancelRename() {
  editingId.value = null
  editTitle.value = ''
}

/** 从菜单触发删除 */
function handleDelete(convId) {
  closeMenu()
  requestDelete(convId)
}

/** 从菜单触发顶置 / 取消顶置 */
function handleTogglePin(conv) {
  closeMenu()
  if (conv.pinned_at) {
    emit('unpin', conv.id)
  } else {
    emit('pin', conv.id)
  }
}
</script>

<style scoped>
.brand-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--success);
  box-shadow: 0 0 8px var(--success-glow);
  animation: pulse-status 2.5s ease-in-out infinite;
}

@keyframes pulse-status {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.45; transform: scale(0.9); }
}

.new-chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.conv-icon {
  flex-shrink: 0;
  opacity: 0.4;
  transition: opacity 0.2s, color 0.2s;
}

.conv-item:hover .conv-icon {
  opacity: 0.7;
}

.conv-item.active .conv-icon {
  opacity: 0.95;
  color: var(--accent);
}

/* ---- 顶置标记 ---- */
.pin-badge {
  flex-shrink: 0;
  color: var(--accent);
  opacity: 0.6;
  margin-left: -2px;
  transition: opacity 0.2s;
}

.conv-item:hover .pin-badge {
  opacity: 0.9;
}

.conv-item.active .pin-badge {
  opacity: 1;
  color: var(--accent);
}

/* 已顶置的会话标题轻微强调 */
.conv-item.pinned .title {
  font-weight: 500;
}

.conv-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 52px 16px;
  color: var(--text-muted);
  font-size: 12px;
}

.rename-wrapper {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.rename-input {
  flex: 1;
  min-width: 0;
  padding: 2px 6px;
  background: var(--bg-input);
  border: 1px solid var(--border-accent);
  border-radius: var(--radius-xxs);
  color: var(--text-primary);
  font-size: 13px;
  font-family: var(--font-ui);
  line-height: 1.4;
  outline: none;
  box-shadow: 0 0 0 3px var(--accent-dim);
}

.rename-counter {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--text-muted);
  opacity: 0.6;
  font-variant-numeric: tabular-nums;
}

/* ---- 三点菜单按钮 ---- */
.more-btn {
  opacity: 0;
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px 6px;
  border-radius: var(--radius-xxs);
  transition: all var(--transition-fast);
  font-family: var(--font-ui);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.conv-item:hover .more-btn { opacity: 0.6; }

.conv-item .more-btn:hover,
.conv-item .more-btn.open {
  opacity: 1 !important;
  color: var(--text-primary);
  background: var(--bg-hover);
}

.sidebar-footer {
  padding: 14px 22px;
  border-top: 1px solid var(--border);
  font-size: 11px;
  color: var(--text-muted);
  opacity: 0.9;
  letter-spacing: 0.3px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: opacity var(--transition-fast);
}

.sidebar-footer:hover {
  opacity: 1;
}

.version-text {
  font-size: 11px;
  color: var(--text-primary);
  font-weight: 500;
}

.settings-btn {
  background: var(--accent-dim);
  border: 1px solid var(--border-accent);
  color: var(--accent);
  cursor: pointer;
  padding: 6px;
  border-radius: var(--radius-xxs);
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 1;
}

.settings-btn:hover {
  background: var(--accent);
  color: var(--bg-base);
  box-shadow: 0 2px 8px var(--accent-glow);
}
</style>

<!-- 全局样式：Teleport 到 body 的菜单元素不能用 scoped -->
<style>
/* ---- 菜单遮罩层 ---- */
.conv-menu-overlay {
  position: fixed;
  inset: 0;
  z-index: 500;
}

/* ---- 下拉菜单 ---- */
.conv-dropdown {
  position: fixed;
  min-width: 140px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xs);
  box-shadow: var(--shadow-float);
  overflow: hidden;
  animation: conv-dropdown-in 0.18s var(--ease-out);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  padding: 4px 0;
}

@keyframes conv-dropdown-in {
  from {
    opacity: 0;
    transform: translateY(-4px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.conv-dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 16px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 13px;
  font-family: var(--font-ui);
  color: var(--text-secondary);
  transition: all var(--transition-fast);
  text-align: left;
}

.conv-dropdown-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.conv-dropdown-item.danger {
  color: var(--danger);
}

.conv-dropdown-item.danger:hover {
  background: var(--danger-dim);
  color: var(--danger);
}

.conv-dropdown-item svg {
  flex-shrink: 0;
  opacity: 0.65;
}

.conv-dropdown-item:hover svg {
  opacity: 1;
}
</style>
