/**
 * 流式 SSE 错误分类与用户友好提示 — Phase 2
 * ============================================
 * 17 种错误类型，每种包含：
 *   - code:        错误标识（与后端 error_code 对应）
 *   - title:       简短标题（显示在消息气泡头部）
 *   - description: 详细说明
 *   - suggestion:  可操作建议
 *   - retryable:   是否值得自动重试
 *
 * 使用方式：
 *   import { classifyStreamError, formatStreamError } from '@/utils/streamErrors';
 *
 *   onError(rawError) {
 *     const info = formatStreamError(rawError);
 *     showErrorBubble(info);
 *   }
 */

// ──────────────────────────────────────────────
// 错误类型
// ──────────────────────────────────────────────

export type StreamErrorCode =
  // 网络层
  | 'NETWORK_TIMEOUT'
  | 'NETWORK_UNREACHABLE'
  | 'CONNECTION_LOST'
  // HTTP 层
  | 'HTTP_BAD_REQUEST'
  | 'HTTP_UNAUTHORIZED'
  | 'HTTP_FORBIDDEN'
  | 'HTTP_NOT_FOUND'
  | 'HTTP_RATE_LIMITED'
  | 'HTTP_SERVER_ERROR'
  // LLM 层
  | 'LLM_UNAVAILABLE'
  | 'LLM_QUOTA_EXCEEDED'
  | 'SQL_GENERATION_FAILED'
  // 数据库层
  | 'DB_CONNECTION'
  | 'DB_QUERY_FAILED'
  | 'DB_PERMISSION'
  // 应用层
  | 'INTENT_AMBIGUOUS'
  | 'STREAM_TERMINATED'
  // 兜底
  | 'UNKNOWN';

export interface StreamErrorInfo {
  /** 与后端 error_code 对齐 */
  code: StreamErrorCode;
  /** 简短标题，用于消息气泡 */
  title: string;
  /** 一句话说明原因 */
  description: string;
  /** 用户可以采取的操作 */
  suggestion: string;
  /** 是否值得页面级自动重试（最多 1 次） */
  retryable: boolean;
  /** 原始错误字符串（保留，用于调试面板） */
  raw?: string;
}

// ──────────────────────────────────────────────
// 错误消息字典
// ──────────────────────────────────────────────

const ERROR_CATALOG: Record<StreamErrorCode, Omit<StreamErrorInfo, 'code' | 'raw'>> = {
  // ── 网络层 ──
  NETWORK_TIMEOUT: {
    title:       '请求超时',
    description: '服务响应时间过长，请求已超时。',
    suggestion:  '请稍后重试，或检查网络连接是否稳定。',
    retryable:   true,
  },
  NETWORK_UNREACHABLE: {
    title:       '网络不可达',
    description: '无法连接到后端服务，请确认服务已启动。',
    suggestion:  '请检查网络设置，或联系管理员确认后端服务状态。',
    retryable:   false,
  },
  CONNECTION_LOST: {
    title:       '连接意外中断',
    description: '与服务的连接在传输过程中断开。',
    suggestion:  '请重新发送请求；若频繁出现，请联系技术支持。',
    retryable:   true,
  },

  // ── HTTP 层 ──
  HTTP_BAD_REQUEST: {
    title:       '请求格式有误',
    description: '服务器无法识别请求内容（400）。',
    suggestion:  '请尝试换一种方式描述您的问题后重试。',
    retryable:   false,
  },
  HTTP_UNAUTHORIZED: {
    title:       '登录已过期',
    description: '当前会话已失效，需要重新登录（401）。',
    suggestion:  '请刷新页面重新登录。',
    retryable:   false,
  },
  HTTP_FORBIDDEN: {
    title:       '无访问权限',
    description: '当前账户无权执行该操作（403）。',
    suggestion:  '请联系管理员申请相应权限。',
    retryable:   false,
  },
  HTTP_NOT_FOUND: {
    title:       '服务接口不存在',
    description: '请求的 API 地址无法找到（404）。',
    suggestion:  '可能是版本不匹配，请联系技术支持。',
    retryable:   false,
  },
  HTTP_RATE_LIMITED: {
    title:       '请求过于频繁',
    description: '短时间内发送了太多请求（429）。',
    suggestion:  '请等待约 1 分钟后再试。',
    retryable:   true,
  },
  HTTP_SERVER_ERROR: {
    title:       '服务器内部错误',
    description: '后端处理请求时发生意外错误（5xx）。',
    suggestion:  '请稍后重试；若持续出现，请记录操作截图并联系技术支持。',
    retryable:   true,
  },

  // ── LLM 层 ──
  LLM_UNAVAILABLE: {
    title:       'AI 服务暂时不可用',
    description: '语言模型服务（DeepSeek / OpenAI）当前无法响应。',
    suggestion:  '请等待 1-2 分钟后重试；若持续失败请联系管理员检查 API 配置。',
    retryable:   true,
  },
  LLM_QUOTA_EXCEEDED: {
    title:       'AI 调用额度已用完',
    description: '语言模型 API 的调用配额已耗尽。',
    suggestion:  '请联系管理员续充 API 额度后再使用。',
    retryable:   false,
  },
  SQL_GENERATION_FAILED: {
    title:       'SQL 生成失败',
    description: 'AI 无法将您的问题转换为有效的数据库查询语句。',
    suggestion:  '请尝试更具体地描述，例如：指明站点名称、时间范围或具体指标。',
    retryable:   false,
  },

  // ── 数据库层 ──
  DB_CONNECTION: {
    title:       '数据库连接失败',
    description: '系统无法连接到生产数据库。',
    suggestion:  '请联系运维人员检查数据库服务状态。',
    retryable:   false,
  },
  DB_QUERY_FAILED: {
    title:       '查询执行失败',
    description: '生成的 SQL 在数据库中执行时出错。',
    suggestion:  '可展开"查询追踪"查看 SQL 详情，手动修改后重试。',
    retryable:   false,
  },
  DB_PERMISSION: {
    title:       '数据库权限不足',
    description: '当前账户无权访问所请求的数据表。',
    suggestion:  '请联系 DBA 授予相应表的查询权限。',
    retryable:   false,
  },

  // ── 应用层 ──
  INTENT_AMBIGUOUS: {
    title:       '问题描述不够清晰',
    description: 'AI 无法确定您想查询的确切内容。',
    suggestion:  '请补充更多信息，例如站点名称、时间区间或具体指标类型。',
    retryable:   false,
  },
  STREAM_TERMINATED: {
    title:       '数据流中断',
    description: '流式传输在完成前意外终止。',
    suggestion:  '请重新发送请求；若反复中断请联系技术支持。',
    retryable:   true,
  },

  // ── 兜底 ──
  UNKNOWN: {
    title:       '出现未知错误',
    description: '处理您的请求时发生了意外情况。',
    suggestion:  '请重试；若问题持续，请联系技术支持并提供操作步骤截图。',
    retryable:   true,
  },
};

// ──────────────────────────────────────────────
// 分类函数
// ──────────────────────────────────────────────

/**
 * 将原始错误字符串（来自 onError 回调）映射到 StreamErrorCode。
 * 优先使用后端返回的 error_code 字段，其次做关键词匹配。
 */
export function classifyStreamError(raw: string): StreamErrorCode {
  // 后端结构化错误优先（error_code 字段）
  const KNOWN_CODES = Object.keys(ERROR_CATALOG) as StreamErrorCode[];
  for (const code of KNOWN_CODES) {
    if (raw.includes(code)) return code;
  }

  const lower = raw.toLowerCase();

  // HTTP 状态码
  if (lower.includes('401')) return 'HTTP_UNAUTHORIZED';
  if (lower.includes('403')) return 'HTTP_FORBIDDEN';
  if (lower.includes('404')) return 'HTTP_NOT_FOUND';
  if (lower.includes('429')) return 'HTTP_RATE_LIMITED';
  if (lower.match(/5\d\d/))  return 'HTTP_SERVER_ERROR';
  if (lower.includes('400')) return 'HTTP_BAD_REQUEST';

  // 网络关键词
  if (lower.includes('timeout') || lower.includes('timed out'))    return 'NETWORK_TIMEOUT';
  if (lower.includes('failed to fetch') || lower.includes('networkerror') || lower.includes('network error'))
    return 'NETWORK_UNREACHABLE';
  if (lower.includes('connection') && lower.includes('lost'))       return 'CONNECTION_LOST';

  // LLM 关键词
  if (lower.includes('quota') || lower.includes('insufficient_quota')) return 'LLM_QUOTA_EXCEEDED';
  if (lower.includes('openai') || lower.includes('deepseek') || lower.includes('api key'))
    return 'LLM_UNAVAILABLE';
  if (lower.includes('sql') && (lower.includes('fail') || lower.includes('invalid') || lower.includes('syntax')))
    return 'SQL_GENERATION_FAILED';

  // 数据库关键词
  if (lower.includes('database') && lower.includes('connect'))     return 'DB_CONNECTION';
  if (lower.includes('permission denied') || lower.includes('access denied')) return 'DB_PERMISSION';
  if (lower.includes('operational') || lower.includes('sql error')) return 'DB_QUERY_FAILED';

  // 流中断
  if (lower.includes('stream') && (lower.includes('end') || lower.includes('terminat')))
    return 'STREAM_TERMINATED';

  return 'UNKNOWN';
}

/**
 * 将原始错误字符串转换为完整的 StreamErrorInfo 对象。
 * 这是组件层调用的主入口。
 */
export function formatStreamError(raw: string): StreamErrorInfo {
  const code = classifyStreamError(raw);
  const catalog = ERROR_CATALOG[code];
  return { code, ...catalog, raw };
}

/**
 * 将 StreamErrorInfo 格式化为适合消息气泡的单行文本。
 * 格式：「[标题] 描述 → 建议」
 */
export function errorToMessageContent(info: StreamErrorInfo): string {
  return `❌ ${info.title}：${info.description} ${info.suggestion}`;
}
