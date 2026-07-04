/**
 * 前端共享工具函数
 * 提取组件间复用的公共逻辑，避免重复定义
 */

import { reactive } from 'vue'

/**
 * 工具名称的中文映射表（响应式）
 * 由后端 API 返回的 display_name 动态填充，不在前端硬编码
 *
 * 数据流：
 *   1. App.vue 调用 loadTools() 从后端获取工具列表（每项含 name + display_name）
 *   2. 调用 registerToolDisplayNames() 将映射写入此响应式对象
 *   3. ChatMessage 等组件通过 toolDisplayName() 读取，Vue 自动追踪依赖
 */
const toolNameMap = reactive({})

/**
 * 批量注册工具显示名称（从后端 API 数据填充）
 * @param {Array} tools - 后端返回的工具列表，每项含 { name, display_name }
 */
export function registerToolDisplayNames(tools) {
  // 清空旧映射（处理工具被删除的情况）
  for (const key of Object.keys(toolNameMap)) {
    delete toolNameMap[key]
  }
  // 写入新映射
  for (const t of tools) {
    if (t.display_name) {
      toolNameMap[t.name] = t.display_name
    }
  }
}

/**
 * 获取工具的展示名称
 * @param {string} name - 工具标识名（如 get_datetime）
 * @returns {string} 中文展示名，未映射时返回原名
 */
export function toolDisplayName(name) {
  return toolNameMap[name] || name
}
