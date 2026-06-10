<!--
  ToolSelector.vue — 下拉多选工具选择器
  放置在输入框底部区域，点击按钮展开浮动面板进行多选
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

    <!-- 整体 Teleport 到 body，避免层叠上下文问题 -->
    <Teleport to="body">
      <template v-if="isOpen">
        <div class="tool-overlay" @click="isOpen = false" />
        <div
          class="tool-dropdown"
          :style="dropdownStyle"
          @click.stop
        >
          <!-- 头部 -->
          <div class="tool-dropdown-header">
            <span>已启用工具</span>
            <button v-if="tools.length > 0" class="toggle-all" @click="toggleAll">
              {{ allSelected ? '取消全选' : '全选' }}
            </button>
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

          <!-- 工具列表 -->
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
              <div class="tool-name">{{ displayName(tool.name) }}</div>
              <div class="tool-desc">{{ shortDesc(tool.description) }}</div>
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
  tools: { type: Array, default: () => [] },
  selected: { type: Array, default: () => [] },
})

const emit = defineEmits(['toggle'])

const isOpen = ref(false)
const triggerRef = ref(null)
const dropdownStyle = ref({})

const allSelected = computed(
  () => props.tools.length > 0 && props.selected.length === props.tools.length
)

async function toggleOpen() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    await nextTick()
    calcPosition()
  }
}

function calcPosition() {
  if (!triggerRef.value) return
  const rect = triggerRef.value.getBoundingClientRect()
  dropdownStyle.value = {
    position: 'fixed',
    left: `${rect.left}px`,
    bottom: `${window.innerHeight - rect.top + 8}px`,
  }
}

function handleResize() {
  if (isOpen.value) calcPosition()
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
})

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

function displayName(name) {
  const map = {
    get_location: '当前位置',
    get_datetime: '当前时间',
    get_weather: '天气查询',
  }
  return map[name] || name
}

function shortDesc(desc) {
  if (!desc) return ''
  const first = desc.split('\n')[0].trim()
  return first.length > 30 ? first.slice(0, 30) + '...' : first
}
</script>

<style scoped>
.icon-svg {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.tool-trigger.open .icon-svg {
  transform: rotate(45deg);
}

.arrow-svg {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.tool-trigger.open .arrow-svg {
  transform: rotate(180deg);
}

.tool-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
</style>
