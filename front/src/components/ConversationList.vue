<!--
  ConversationList.vue — 侧边栏会话列表

  展示所有历史会话，支持：
    - 新建对话（emit new-chat）
    - 选择会话（emit select）
    - 删除会话（emit delete）
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
        :class="{ active: conv.id === currentId }"
        @click="$emit('select', conv.id)"
      >
        <svg class="conv-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <span class="title">{{ conv.title || '新对话' }}</span>
        <!-- 删除按钮（hover 时显示） -->
        <button
          class="delete-btn"
          @click.stop="$emit('delete', conv.id)"
          title="删除"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <!-- 空状态 -->
      <div v-if="conversations.length === 0" class="conv-empty">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.3">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <span>暂无对话记录</span>
      </div>
    </div>

    <!-- 底部信息 -->
    <div class="sidebar-footer">
      <span>ZpAgent v1.0</span>
    </div>
  </aside>
</template>

<script setup>
defineProps({
  conversations: { type: Array, default: () => [] },
  currentId:     { type: String, default: null },
})

defineEmits(['select', 'new-chat', 'delete'])
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

.conv-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 52px 16px;
  color: var(--text-muted);
  font-size: 12px;
}

.sidebar-footer {
  padding: 14px 22px;
  border-top: 1px solid var(--border);
  font-size: 11px;
  color: var(--text-muted);
  opacity: 0.45;
  letter-spacing: 0.3px;
}
</style>
