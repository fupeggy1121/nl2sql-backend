// src/utils/sqlFilterInjector.ts
// Injects DashboardFilter values into a saved SQL string (client-side WHERE injection).
// Strategy: find existing WHERE clause → AND append; no WHERE → insert before GROUP BY / ORDER BY / HAVING / LIMIT / end.

import { DashboardFilter } from '../types/dashboard'

/** Build a single SQL condition string from a filter value. Returns null if no value. */
function buildCondition(filter: DashboardFilter): string | null {
  const val = filter.value ?? filter.defaultValue
  if (!val || val.trim() === '') return null

  const col = filter.sqlColumn

  if (filter.type === 'date-range') {
    // Expected format: "YYYY-MM-DD,YYYY-MM-DD"
    const parts = val.split(',')
    if (parts.length === 2) {
      const [start, end] = parts.map(p => p.trim())
      if (start && end) return `${col} BETWEEN '${start}' AND '${end}'`
      if (start) return `${col} >= '${start}'`
      if (end) return `${col} <= '${end}'`
    }
    return null
  }

  if (filter.type === 'select') {
    // May be comma-separated multiple values
    const vals = val.split(',').map(v => v.trim()).filter(Boolean)
    if (vals.length === 0) return null
    if (vals.length === 1) return `${col} = '${vals[0]}'`
    const inList = vals.map(v => `'${v}'`).join(', ')
    return `${col} IN (${inList})`
  }

  // text: simple LIKE or =
  if (val.includes('%')) return `${col} LIKE '${val}'`
  return `${col} = '${val}'`
}

/**
 * Merge global + local filters. When both define a condition for the same sqlColumn,
 * the local filter wins (it overrides the global one).
 */
export function mergeFilters(
  globalFilters: DashboardFilter[],
  localFilters: DashboardFilter[],
): DashboardFilter[] {
  const localCols = new Set(localFilters.map(f => f.sqlColumn))
  const filtered = globalFilters.filter(f => !localCols.has(f.sqlColumn))
  return [...filtered, ...localFilters]
}

/**
 * Inject active filter conditions into a SQL string.
 * Only filters that have a value (or defaultValue) produce conditions.
 */
export function injectFilters(sql: string, filters: DashboardFilter[]): string {
  const conditions = filters
    .map(buildCondition)
    .filter((c): c is string => c !== null)

  if (conditions.length === 0) return sql

  const conditionStr = conditions.join(' AND ')

  // Normalise whitespace for regex matching
  const s = sql.trim()

  // Case 1: Already has a WHERE clause
  // Insert after WHERE keyword, before any following GROUP BY / HAVING / ORDER BY / LIMIT
  const whereRegex = /\bWHERE\b/i
  if (whereRegex.test(s)) {
    // Find where conditions end (before GROUP BY / HAVING / ORDER BY / LIMIT)
    const afterWhere = s.replace(
      /(\bWHERE\b)([\s\S]*?)(\b(?:GROUP\s+BY|HAVING|ORDER\s+BY|LIMIT)\b|$)/i,
      (_match, where, existingConds, tail) => {
        const trimmedConds = existingConds.trimEnd()
        return `${where}${trimmedConds} AND ${conditionStr} ${tail}`
      }
    )
    return afterWhere.trim()
  }

  // Case 2: No WHERE clause - insert before GROUP BY / HAVING / ORDER BY / LIMIT
  const insertBeforeRegex = /\b(GROUP\s+BY|HAVING|ORDER\s+BY|LIMIT)\b/i
  const match = insertBeforeRegex.exec(s)
  if (match && match.index !== undefined) {
    const before = s.slice(0, match.index).trimEnd()
    const after = s.slice(match.index)
    return `${before}\nWHERE ${conditionStr}\n${after}`
  }

  // Case 3: Fallback - append to end
  return `${s}\nWHERE ${conditionStr}`
}
