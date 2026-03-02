/**
 * 统一NL2SQL API 服务
 * 与后端统一查询服务交互
 * 
 * 流程:
 * 1. 前端发送自然语言查询到后端
 * 2. 后端识别意图、生成SQL、可选执行
 * 3. 后端返回查询计划和可选结果
 * 4. 前端展示SQL供用户审核
 * 5. 用户批准后，前端请求执行
 * 6. 后端执行并返回结果
 */
import { checkHealth } from './api';

// 支持 Vite 的 VITE_API_BASE_URL 和 React 的 REACT_APP_API_URL 两种方式
const getApiBaseUrl = () => {
  if (typeof import.meta !== 'undefined' && import.meta?.env?.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  // React 环境变量降级
  if (typeof process !== 'undefined' && process.env?.REACT_APP_API_URL) {
    return `${process.env.REACT_APP_API_URL}/api/query/unified`;
  }
  // 本地开发默认值
  return 'http://localhost:8000/api/query/unified';
};

const UNIFIED_API_URL = getApiBaseUrl();

export interface QueryIntent {
  query_type: string;
  natural_language: string;
  metric?: string;
  time_range?: string;
  equipment?: string[];
  shift?: string[];
  table_name?: string;
  comparison: boolean;
  confidence: number;
  clarification_needed: boolean;
  clarification_questions?: string[];
}

export interface QueryPlan {
  query_intent: QueryIntent;
  generated_sql?: string;
  sql_confidence: number;
  requires_clarification: boolean;
  clarification_message?: string;
  suggested_sql_variants?: string[];
  schema_context?: any;
  explanation?: string;
}

export interface QueryResult {
  success: boolean;
  data: any[];
  sql: string;
  rows_count: number;
  summary: string;
  visualization_type: 'table' | 'bar' | 'line' | 'pie' | 'gauge';
  actions: string[];
  error_message?: string;
  query_time_ms: number;
  generated_at: string;
}

/** 管道追踪步骤 */
export interface PipelineTraceStep {
  step: string;
  elapsed_ms: number;
  summary: string;
  status: 'ok' | 'warn' | 'error';
  detail?: Record<string, any>;
}

/**
 * 可视化配置接口，与后端返回的 visualization 对象结构一致
 */
export interface VisualizationConfig {
  type: string;               // 图表类型，如 'bar', 'line', 'pie', 'table' 等
  title?: string;             // 图表标题
  xAxisField?: string;        // X轴字段名
  yAxisField?: string;        // Y轴字段名（单值图表）
  yAxisFields?: string[];     // 多Y轴字段（备用）
  seriesField?: string;       // 分组/系列字段
  confidence: number;         // 可视化推荐的置信度
  reason?: string;            // 选择此可视化类型的理由
  // 可能还有其他可选字段，根据需要扩展
  [key: string]: any;
}

export interface UnifiedQueryResponse {
  success: boolean;
  session_id?: string;          // 后端返回的会话ID，前端应保存用于后续追问
  is_followup?: boolean;         // 是否为追问（后端自动检测）
  query_plan?: QueryPlan;
  query_result?: QueryResult;
  pipeline_trace?: PipelineTraceStep[];  // 管道追踪（可展开查看完整流水线）
  visualization?: VisualizationConfig;    // 后端返回的可视化配置信息（可选）
  error?: string;
}

/**
 * 处理自然语言查询
 * 支持两种模式:
 * - explain: 只返回SQL解释
 * - execute: 直接执行并返回结果
 *
 * @param sessionId - 可选，传入已有 session_id 可启用多轮对话记忆。
 *                     首次查询不传，后续追问传入上次响应返回的 session_id。
 */
export async function processNaturalLanguageQuery(
  naturalLanguage: string,
  executionMode: 'explain' | 'execute' = 'explain',
  userContext?: any,
  sessionId?: string
): Promise<UnifiedQueryResponse> {
  try {
    const payload: any = {
      natural_language: naturalLanguage,
      execution_mode: executionMode,
      user_context: userContext,
    };
    // 传入 session_id 启用多轮对话上下文
    if (sessionId) {
      payload.session_id = sessionId;
    }

    const response = await fetch(`${UNIFIED_API_URL}/process`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || `HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error processing natural language query:', error);
    throw error;
  }
}

/**
 * 只获取SQL解释（不执行）
 * @param sessionId - 可选会话ID，用于多轮对话追问
 */
export async function explainQuery(naturalLanguage: string, sessionId?: string): Promise<UnifiedQueryResponse> {
  return processNaturalLanguageQuery(naturalLanguage, 'explain', undefined, sessionId);
}

/**
 * 执行已批准的SQL查询
 */
export async function executeApprovedQuery(
  sql: string,
  queryIntent?: QueryIntent
): Promise<UnifiedQueryResponse> {
  try {
    const response = await fetch(`${UNIFIED_API_URL}/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        sql,
        query_intent: queryIntent
      })
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || `HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error executing approved query:', error);
    throw error;
  }
}

/**
 * 建议SQL变体
 */
export async function suggestSQLVariants(
  naturalLanguage: string,
  baseSQL: string
): Promise<{ success: boolean; variants: any[] }> {
  try {
    const response = await fetch(`${UNIFIED_API_URL}/suggest-variants`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        natural_language: naturalLanguage,
        base_sql: baseSQL
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error suggesting SQL variants:', error);
    throw error;
  }
}

/**
 * 验证SQL语法和合理性
 */
export async function validateSQL(sql: string): Promise<{
  success: boolean;
  is_valid: boolean;
  errors: string[];
  warnings: string[];
}> {
  try {
    const response = await fetch(`${UNIFIED_API_URL}/validate-sql`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ sql })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error validating SQL:', error);
    throw error;
  }
}

/**
 * 获取查询执行历史
 */
export async function getExecutionHistory(
  limit: number = 20,
  offset: number = 0
): Promise<{ success: boolean; history: any[]; total: number }> {
  try {
    const response = await fetch(
      `${UNIFIED_API_URL}/execution-history?limit=${limit}&offset=${offset}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        }
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error getting execution history:', error);
    throw error;
  }
}

/**
 * 获取查询建议
 */
export async function getQueryRecommendations(): Promise<{
  success: boolean;
  recommendations: any[];
}> {
  try {
    const response = await fetch(`${UNIFIED_API_URL}/query-recommendations`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error getting query recommendations:', error);
    throw error;
  }
}

/**
 * 完整的查询流程
 * 1. 解析自然语言，生成SQL
 * 2. 返回SQL供用户审核
 * 3. 用户批准后执行
 */
export async function executeQueryWithApproval(
  naturalLanguage: string,
  onSQLReady: (sql: string, explanation: string) => Promise<boolean>,
  userContext?: any,
  sessionId?: string
): Promise<QueryResult> {
  // 步骤1: 获取SQL解释
  const explainResponse = await explainQuery(naturalLanguage, sessionId);

  if (!explainResponse.success) {
    throw new Error(explainResponse.error || '查询失败');
  }

  const queryPlan = explainResponse.query_plan;

  if (queryPlan.requires_clarification) {
    throw new Error(queryPlan.clarification_message || '需要澄清查询意图');
  }

  const sql = queryPlan.generated_sql;
  const explanation = queryPlan.explanation;

  if (!sql) {
    throw new Error('无法生成SQL');
  }

  // 步骤2: 等待用户批准
  const isApproved = await onSQLReady(sql, explanation);

  if (!isApproved) {
    throw new Error('用户拒绝执行');
  }

  // 步骤3: 执行查询
  const executeResponse = await executeApprovedQuery(sql, queryPlan.query_intent);

  if (!executeResponse.success) {
    throw new Error(executeResponse.error || '查询执行失败');
  }

  return executeResponse.query_result!;
}

/**
 * 根据建议查询执行
 */
export async function executeRecommendedQuery(
  recommendation: any,
  onSQLReady?: (sql: string, explanation: string) => Promise<boolean>
): Promise<QueryResult> {
  return executeQueryWithApproval(
    recommendation.natural_language,
    onSQLReady || (async () => true) // 自动批准建议查询
  );
}

/**
 * 检查后端连接状态
 */
export async function checkConnection(): Promise<{ connected: boolean; message?: string }> {
  try {
    const response = await fetch(`${UNIFIED_API_URL}/health`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) {
      return { connected: false, message: `HTTP ${response.status}` };
    }
    const data = await response.json();
    return { connected: true, message: data.status || 'healthy' };
  } catch (error) {
    return { connected: false, message: String(error) };
  }
}

export const nl2sqlApi = {
  processNaturalLanguageQuery,
  explainQuery,
  executeApprovedQuery,
  suggestSQLVariants,
  validateSQL,
  getExecutionHistory,
  getQueryRecommendations,
  executeQueryWithApproval,
  executeRecommendedQuery,
  checkConnection,
};

export default nl2sqlApi;