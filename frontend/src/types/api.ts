export interface QueryIntent {
  success: boolean
  error?: string
  intent: string
  confidence: number
  entities: Record<string, unknown>
}

export interface SelfCorrection {
  retries: number
  note: string
}

export interface QueryPlan {
  query_intent: QueryIntent
  generated_sql: string
  sql_confidence: number
  explanation: string
  self_correction?: SelfCorrection
}

export interface QueryResult {
  success: boolean
  data: Record<string, unknown>[]
  rows_count: number
  sql: string
  summary: string
  visualization_type: 'table' | 'bar' | 'pie' | 'line'
  query_time_ms: number
  error?: string
}

export interface LlmTokenUsage {
  input: number
  output: number
  total: number
}

export interface PipelineStep {
  step: string
  elapsed_ms: number
  summary: string
  status: 'ok' | 'warn' | 'error' | 'skip'
  detail?: Record<string, unknown>
  llm_tokens?: LlmTokenUsage
}

export interface ProcessResponse {
  success: boolean
  session_id: string
  query_plan: QueryPlan
  query_result?: QueryResult
  pipeline_trace: PipelineStep[]
  error?: string
}

export interface ExecuteResponse {
  success: boolean
  data: Record<string, unknown>[]
  rows_count: number
  sql: string
  summary: string
  visualization_type: 'table' | 'bar' | 'pie' | 'line'
  query_time_ms: number
  error?: string
}

export interface Recommendation {
  category: string
  queries: string[]
}

export interface DbMode {
  mapping: {
    mode: string
    source: string
    file: string
  }
  database: {
    mode: string
    source: string
    runtime_db_mode: string | null
    db_backend: string   // "mysql" | "supabase"
  }
}
