import { useEffect, useState, type KeyboardEvent } from 'react'
import { Search, Loader2 } from 'lucide-react'
import { getRecommendations } from '../api/nl2sql'
import type { Recommendation } from '../types/api'

interface Props {
  onQuery: (query: string) => void
  loading: boolean
}

export function QueryInput({ onQuery, loading }: Props) {
  const [value, setValue] = useState('')
  const [recs, setRecs] = useState<Recommendation[]>([])

  useEffect(() => {
    getRecommendations()
      .then(r => setRecs(r.recommendations))
      .catch(() => {})
  }, [])

  const submit = () => {
    const q = value.trim()
    if (q && !loading) onQuery(q)
  }

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Recommendation chips */}
      {recs.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {recs.map(cat => (
            <div key={cat.category}>
              <span style={{ fontSize: 12, color: '#6b7280', fontWeight: 600 }}>
                {cat.category}
              </span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
                {cat.queries.map(q => (
                  <button
                    key={q}
                    onClick={() => { setValue(q); onQuery(q) }}
                    disabled={loading}
                    style={{
                      padding: '4px 10px',
                      borderRadius: 14,
                      border: '1px solid #e0e7ff',
                      background: '#f5f3ff',
                      color: '#4f46e5',
                      fontSize: 13,
                      cursor: 'pointer',
                      transition: 'background .15s',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = '#ede9fe')}
                    onMouseLeave={e => (e.currentTarget.style.background = '#f5f3ff')}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Input + button */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
        <textarea
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={onKey}
          placeholder="输入自然语言查询，例如：查询今天的生产产量…（Enter 发送，Shift+Enter 换行）"
          rows={3}
          style={{
            flex: 1,
            padding: '12px 16px',
            borderRadius: 10,
            border: '1.5px solid #e5e7eb',
            fontSize: 15,
            resize: 'vertical',
            outline: 'none',
            lineHeight: 1.5,
            transition: 'border-color .2s',
            fontFamily: 'inherit',
          }}
          onFocus={e => (e.currentTarget.style.borderColor = '#4f46e5')}
          onBlur={e => (e.currentTarget.style.borderColor = '#e5e7eb')}
          disabled={loading}
        />
        <button
          onClick={submit}
          disabled={loading || !value.trim()}
          style={{
            padding: '12px 22px',
            borderRadius: 10,
            border: 'none',
            background: loading || !value.trim() ? '#c7d2fe' : '#4f46e5',
            color: '#fff',
            fontSize: 15,
            fontWeight: 600,
            cursor: loading || !value.trim() ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            transition: 'background .2s',
            whiteSpace: 'nowrap',
          }}
        >
          {loading ? (
            <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} />
          ) : (
            <Search size={18} />
          )}
          {loading ? '查询中…' : '查询'}
        </button>
      </div>
    </div>
  )
}
