<!--
  ApprovalPanel.vue — HITL 人工审批面板

  当 Agent 的工具调用需要人工审批时，展示在消息列表底部。
  每个待审批的工具调用显示为一个卡片，包含：
    - 工具名称和参数
    - 三个操作按钮：同意 / 编辑参数 / 拒绝
    - 编辑模式：展开 JSON 编辑器修改参数
    - 拒绝模式：展开文本框输入拒绝原因

  所有决策收集完毕后，点击"提交决策"按钮一次性提交。
-->
<template>
  <div class="approval-panel">
    <div class="approval-header">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      </svg>
      <span>需要审批确认（{{ actions.length }} 个工具调用）</span>
    </div>

    <!-- 每个待审批的工具调用 -->
    <div
      v-for="(action, idx) in actions"
      :key="idx"
      class="approval-card"
    >
      <!-- 工具信息 -->
      <div class="approval-tool-info">
        <span class="tool-badge">{{ action.name }}</span>
        <pre class="tool-args">{{ formatArgs(action.args) }}</pre>
      </div>

      <!-- 已做出的决策状态显示 -->
      <div v-if="decisions[idx]" class="decision-status" :class="decisions[idx].type">
        <span v-if="decisions[idx].type === 'approve'">&#10003; 已同意</span>
        <span v-else-if="decisions[idx].type === 'edit'">&#9998; 已编辑参数</span>
        <span v-else-if="decisions[idx].type === 'reject'">&#10007; 已拒绝{{ decisions[idx].message ? '：' + decisions[idx].message : '' }}</span>
      </div>

      <!-- 操作按钮组 -->
      <div v-else class="approval-actions">
        <!-- 同意按钮 -->
        <button
          v-if="action.allowed_decisions.includes('approve')"
          class="approve-btn"
          @click="makeDecision(idx, 'approve')"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          同意
        </button>

        <!-- 编辑参数按钮 -->
        <button
          v-if="action.allowed_decisions.includes('edit')"
          class="edit-btn"
          @click="toggleEditMode(idx)"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
          编辑参数
        </button>

        <!-- 拒绝按钮 -->
        <button
          v-if="action.allowed_decisions.includes('reject')"
          class="reject-btn"
          @click="toggleRejectMode(idx)"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
          拒绝
        </button>
      </div>

      <!-- 编辑模式：JSON 参数编辑器 -->
      <div v-if="editingIdx === idx" class="edit-area">
        <textarea
          v-model="editBuffer"
          class="edit-textarea"
          rows="4"
          spellcheck="false"
        />
        <div class="edit-confirm-row">
          <button class="edit-confirm-btn" @click="confirmEdit(idx)">确认修改</button>
          <button class="edit-cancel-btn" @click="editingIdx = -1">取消</button>
        </div>
      </div>

      <!-- 拒绝模式：输入拒绝原因 -->
      <div v-if="rejectingIdx === idx" class="reject-area">
        <textarea
          v-model="rejectBuffer"
          class="reject-textarea"
          placeholder="请输入拒绝原因（可选）..."
          rows="2"
        />
        <div class="edit-confirm-row">
          <button class="reject-confirm-btn" @click="confirmReject(idx)">确认拒绝</button>
          <button class="edit-cancel-btn" @click="rejectingIdx = -1">取消</button>
        </div>
      </div>
    </div>

    <!-- 提交按钮 -->
    <button
      class="submit-decisions-btn"
      :disabled="!allDecided"
      @click="handleSubmit"
    >
      提交决策（{{ decidedCount }}/{{ actions.length }}）
    </button>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  // 待审批的工具调用列表，每项包含 name、args、description、allowed_decisions
  actions: { type: Array, required: true },
})

const emit = defineEmits(['submit'])

// 决策结果数组，与 actions 一一对应
const decisions = ref(new Array(props.actions.length).fill(null))

// 编辑模式状态
const editingIdx = ref(-1)
const editBuffer = ref('')

// 拒绝模式状态
const rejectingIdx = ref(-1)
const rejectBuffer = ref('')

// 是否所有工具都已做出决策
const decidedCount = computed(() => decisions.value.filter(d => d !== null).length)
const allDecided = computed(() => decidedCount.value === props.actions.length)

/** 格式化参数为 JSON 字符串 */
function formatArgs(args) {
  if (!args) return '{}'
  try { return JSON.stringify(args, null, 2) }
  catch { return String(args) }
}

/** 直接同意 */
function makeDecision(idx, type) {
  decisions.value[idx] = { type }
}

/** 切换到编辑模式 */
function toggleEditMode(idx) {
  editingIdx.value = idx
  editBuffer.value = formatArgs(props.actions[idx].args)
}

/** 确认编辑：验证 JSON 格式后设置决策 */
function confirmEdit(idx) {
  try {
    const newArgs = JSON.parse(editBuffer.value)
    decisions.value[idx] = {
      type: 'edit',
      edited_action: {
        name: props.actions[idx].name,
        args: newArgs,
      },
    }
    editingIdx.value = -1
  } catch (e) {
    alert('JSON 格式错误，请检查：' + e.message)
  }
}

/** 切换到拒绝模式 */
function toggleRejectMode(idx) {
  rejectingIdx.value = idx
  rejectBuffer.value = ''
}

/** 确认拒绝 */
function confirmReject(idx) {
  const decision = { type: 'reject' }
  if (rejectBuffer.value.trim()) {
    decision.message = rejectBuffer.value.trim()
  }
  decisions.value[idx] = decision
  rejectingIdx.value = -1
}

/** 提交所有决策 */
function handleSubmit() {
  if (!allDecided.value) return
  emit('submit', decisions.value)
}
</script>
