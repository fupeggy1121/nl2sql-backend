// src/services/api.ts — local health check helper
const BASE = 'http://localhost:8000/api/query/unified';

export async function checkHealth(): Promise<{ healthy: boolean; db_backend?: string }> {
  try {
    const res = await fetch(BASE + '/health', { signal: AbortSignal.timeout(5000) });
    if (!res.ok) return { healthy: false };
    const data = await res.json();
    return { healthy: data.status === 'healthy', db_backend: data.db_backend };
  } catch {
    return { healthy: false };
  }
}
