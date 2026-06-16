/**
 * 前端共享工具函数
 * 提取组件间复用的公共逻辑，避免重复定义
 */

/**
 * 工具名称的中文映射表
 * 将后端工具标识名转换为前端展示用的中文名称
 */
const TOOL_NAME_MAP = {
  get_location: '当前位置',
  get_datetime: '当前时间',
  get_weather: '天气查询',
}

/**
 * 获取工具的展示名称
 * @param {string} name - 工具标识名（如 get_weather）
 * @returns {string} 中文展示名，未映射时返回原名
 */
export function toolDisplayName(name) {
  return TOOL_NAME_MAP[name] || name
}
