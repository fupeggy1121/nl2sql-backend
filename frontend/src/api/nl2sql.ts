import type {
  ProcessResponse,
  ExecuteResponse,
  Recommendation,
  DbMode,
} from '../types/api'

// In dev, Vite proxy forwards /api → localhost:8000
// In production (Vercel/Netlify), set VITE_API_BASE or use full domain
const BASE = import.meta.env.VITE_API_BASE ?? ''

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

/** 自然语言 → SQL (不立即执行) */
export async function processQuery(
  naturalLanguage: string,
  sessionId?: string
): Promise<ProcessResponse> {
  return post('/api/query/unified/process', {
    natural_language: naturalLanguage,
    execute_immediately: false,
    session_id: sessionId,
  })
}

/** 执行 SQL 并返回数据 */
export async function executeQuery(
  sql: string,
  sessionId?: string
): Promise<ExecuteResponse> {
  return post('/api/query/unified/execute', {
    sql,
    session_id: sessionId,
  })
}

/** 推荐查询列表 */
export async function getRecommendations(): Promise<{
  success: boolean
  recommendations: Recommendation[]
}> {
  return get('/api/query/unified/query-recommendations')
}

/** 当前 DB 模式 */
export async function getDbMode(): Promise<{ data: DbMode }> {
  return get('/api/mapping/mode')
}

/** 切换 DB 模式: mysql | supabase | auto */
export async function switchDbMode(mode: string): Promise<unknown> {
  return post('/api/mapping/switch', { db_mode: mode })
}
