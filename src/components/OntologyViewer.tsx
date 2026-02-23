/**
 * OntologyViewer.tsx — 本体可视化 & TTL 版本管理 React 组件
 *
 * 用于 Bolt.new 前端集成。
 *
 * 功能：
 *   - 嵌入后端 ontology-viewer 页面（D3 力导向图）
 *   - 版本历史面板（查看 / 回滚）
 *   - TTL 文件上传弹窗
 *   - 一键刷新 / 热重载
 *
 * 依赖: lucide-react (已在项目中使用)
 *
 * 使用方式:
 *   import OntologyViewer from './OntologyViewer';
 *   <OntologyViewer />
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Upload, RefreshCw, History, RotateCcw, Eye, X,
  FileText, Clock, User, HardDrive, ChevronRight,
  AlertCircle, CheckCircle, Info, Loader2
} from 'lucide-react';
import { ontologyApi, getViewerUrl } from '../services/ontologyApi';

// ─── Types ────────────────────────────────────

interface Version {
  version: number;
  filename: string;
  timestamp: string;
  message: string;
  author: string;
  size_bytes: number;
}

interface Toast {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info';
}

// ─── Main Component ───────────────────────────

export default function OntologyViewer() {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // State
  const [showVersionPanel, setShowVersionPanel] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [versions, setVersions] = useState<Version[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadMessage, setUploadMessage] = useState('');
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [summary, setSummary] = useState<any>(null);

  // ─── Toast ──────────────────────────────────
  const addToast = useCallback((message: string, type: Toast['type'] = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  }, []);

  // ─── Data fetching ──────────────────────────
  const loadSummary = useCallback(async () => {
    try {
      const data = await ontologyApi.getSummary();
      setSummary(data);
    } catch (e: any) {
      console.error('Load summary failed:', e);
    }
  }, []);

  const loadVersions = useCallback(async () => {
    setVersionsLoading(true);
    try {
      const data = await ontologyApi.listVersions();
      setVersions(data.versions || []);
    } catch (e: any) {
      addToast('加载版本历史失败: ' + e.message, 'error');
    } finally {
      setVersionsLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    if (showVersionPanel) loadVersions();
  }, [showVersionPanel, loadVersions]);

  // ─── Actions ────────────────────────────────
  const refreshViewer = useCallback(() => {
    if (iframeRef.current) {
      iframeRef.current.src = getViewerUrl();
    }
    loadSummary();
    addToast('已刷新', 'info');
  }, [loadSummary, addToast]);

  const handleReload = useCallback(async () => {
    try {
      await ontologyApi.reload();
      refreshViewer();
      addToast('热重载完成', 'success');
    } catch (e: any) {
      addToast('热重载失败: ' + e.message, 'error');
    }
  }, [refreshViewer, addToast]);

  const handleUpload = useCallback(async () => {
    if (!uploadFile) return;
    setUploading(true);
    try {
      const data = await ontologyApi.uploadTTL(uploadFile, uploadMessage);
      addToast(data.message || `已保存为 v${data.version?.version}`, 'success');
      setShowUploadModal(false);
      setUploadFile(null);
      setUploadMessage('');
      refreshViewer();
      if (showVersionPanel) loadVersions();
    } catch (e: any) {
      addToast('上传失败: ' + e.message, 'error');
    } finally {
      setUploading(false);
    }
  }, [uploadFile, uploadMessage, refreshViewer, showVersionPanel, loadVersions, addToast]);

  const handleRollback = useCallback(async (version: number) => {
    if (!confirm(`确定回滚到版本 v${version}？\n将创建新版本记录并恢复历史内容。`)) return;
    try {
      const data = await ontologyApi.rollback(version);
      addToast(data.message || `已回滚到 v${version}`, 'success');
      refreshViewer();
      loadVersions();
    } catch (e: any) {
      addToast('回滚失败: ' + e.message, 'error');
    }
  }, [refreshViewer, loadVersions, addToast]);

  const handleViewVersion = useCallback(async (version: number) => {
    try {
      const data = await ontologyApi.getVersion(version);
      // 通过 postMessage 传给 iframe，或直接打开新窗口
      const blob = new Blob([data.content], { type: 'text/turtle' });
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
      addToast(`已在新窗口打开 v${version}`, 'info');
    } catch (e: any) {
      addToast('加载版本失败: ' + e.message, 'error');
    }
  }, [addToast]);

  // ─── Helpers ────────────────────────────────
  const formatTime = (iso: string) => {
    if (!iso) return '';
    return new Date(iso).toLocaleString('zh-CN', {
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    });
  };

  const formatBytes = (b: number) => {
    if (b < 1024) return b + ' B';
    if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' KB';
    return (b / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const maxVersion = versions.length > 0 ? Math.max(...versions.map(v => v.version)) : 0;

  // ─── Render ─────────────────────────────────
  return (
    <div style={styles.container}>
      {/* ── Toolbar ── */}
      <div style={styles.toolbar}>
        <div style={styles.toolbarLeft}>
          <h2 style={styles.title}>
            <FileText size={20} />
            本体可视化
          </h2>
          {summary && (
            <div style={styles.statsRow}>
              <span style={styles.stat}>
                类: <b style={styles.statValue}>{summary.ontology?.classes ?? '-'}</b>
              </span>
              <span style={styles.stat}>
                关系: <b style={styles.statValue}>{summary.ontology?.relations ?? '-'}</b>
              </span>
              <span style={styles.stat}>
                映射: <b style={styles.statValue}>{summary.mapping?.object_mappings ?? '-'}</b>
              </span>
            </div>
          )}
        </div>
        <div style={styles.toolbarRight}>
          <button style={styles.btnPrimary} onClick={() => setShowUploadModal(true)}>
            <Upload size={14} /> 上传 TTL
          </button>
          <button style={styles.btn} onClick={handleReload}>
            <RefreshCw size={14} /> 热重载
          </button>
          <button
            style={{ ...styles.btn, ...(showVersionPanel ? styles.btnActive : {}) }}
            onClick={() => setShowVersionPanel(v => !v)}
          >
            <History size={14} /> 版本历史
          </button>
        </div>
      </div>

      {/* ── Main area ── */}
      <div style={styles.main}>
        {/* Viewer iframe */}
        <div style={styles.viewerWrap}>
          <iframe
            ref={iframeRef}
            src={getViewerUrl()}
            style={styles.iframe}
            title="Ontology Viewer"
          />
        </div>

        {/* Version panel */}
        {showVersionPanel && (
          <div style={styles.versionPanel}>
            <div style={styles.vPanelHeader}>
              <h3 style={styles.vPanelTitle}>版本历史</h3>
              <button style={styles.closeBtn} onClick={() => setShowVersionPanel(false)}>
                <X size={16} />
              </button>
            </div>
            <div style={styles.versionList}>
              {versionsLoading ? (
                <div style={styles.centerText}>
                  <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} />
                  <span>加载中...</span>
                </div>
              ) : versions.length === 0 ? (
                <div style={styles.centerText}>
                  <Info size={16} />
                  <span>暂无版本记录<br />上传第一个 TTL 后自动创建</span>
                </div>
              ) : (
                versions.map(v => (
                  <div
                    key={v.version}
                    style={{
                      ...styles.versionCard,
                      ...(v.version === maxVersion ? styles.versionCardActive : {}),
                    }}
                  >
                    <div style={styles.vCardHeader}>
                      <span style={styles.vNum}>v{v.version}</span>
                      {v.version === maxVersion ? (
                        <span style={styles.badgeCurrent}>当前</span>
                      ) : (
                        <span style={styles.badge}>历史</span>
                      )}
                    </div>
                    <div style={styles.vMsg}>{v.message}</div>
                    <div style={styles.vMeta}>
                      <span><Clock size={11} /> {formatTime(v.timestamp)}</span>
                      <span><User size={11} /> {v.author}</span>
                      <span><HardDrive size={11} /> {formatBytes(v.size_bytes)}</span>
                    </div>
                    <div style={styles.vActions}>
                      <button style={styles.btnSm} onClick={() => handleViewVersion(v.version)}>
                        <Eye size={12} /> 查看
                      </button>
                      {v.version !== maxVersion && (
                        <button
                          style={{ ...styles.btnSm, ...styles.btnSmDanger }}
                          onClick={() => handleRollback(v.version)}
                        >
                          <RotateCcw size={12} /> 回滚
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Upload Modal ── */}
      {showUploadModal && (
        <div style={styles.overlay} onClick={() => setShowUploadModal(false)}>
          <div style={styles.modal} onClick={e => e.stopPropagation()}>
            <h3 style={styles.modalTitle}>
              <Upload size={18} /> 上传新 TTL 文件
            </h3>

            {/* Drop zone */}
            <div
              style={styles.dropZone}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={e => { e.preventDefault(); e.currentTarget.style.borderColor = '#0ea5e9'; }}
              onDragLeave={e => { e.currentTarget.style.borderColor = '#475569'; }}
              onDrop={e => {
                e.preventDefault();
                e.currentTarget.style.borderColor = '#475569';
                const f = e.dataTransfer.files[0];
                if (f && (f.name.endsWith('.ttl') || f.name.endsWith('.turtle'))) setUploadFile(f);
              }}
            >
              {uploadFile ? (
                <>
                  <CheckCircle size={28} color="#22c55e" />
                  <span style={styles.dropFileName}>{uploadFile.name}</span>
                  <span style={styles.dropFileSize}>{formatBytes(uploadFile.size)}</span>
                </>
              ) : (
                <>
                  <Upload size={28} color="#64748b" />
                  <span style={styles.dropText}>拖拽 .ttl 文件到此处，或点击选择</span>
                </>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".ttl,.turtle"
              style={{ display: 'none' }}
              onChange={e => e.target.files?.[0] && setUploadFile(e.target.files[0])}
            />

            {/* Message */}
            <div style={styles.formGroup}>
              <label style={styles.label}>版本说明</label>
              <textarea
                style={styles.textarea}
                placeholder="描述本次修改内容..."
                value={uploadMessage}
                onChange={e => setUploadMessage(e.target.value)}
              />
            </div>

            {/* Buttons */}
            <div style={styles.modalBtnRow}>
              <button style={styles.btn} onClick={() => { setShowUploadModal(false); setUploadFile(null); }}>
                取消
              </button>
              <button
                style={{ ...styles.btnPrimary, opacity: !uploadFile || uploading ? 0.5 : 1 }}
                disabled={!uploadFile || uploading}
                onClick={handleUpload}
              >
                {uploading ? <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> 上传中...</> : '上传并应用'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Toasts ── */}
      <div style={styles.toastContainer}>
        {toasts.map(t => (
          <div key={t.id} style={{ ...styles.toast, ...styles[`toast_${t.type}`] }}>
            {t.type === 'success' && <CheckCircle size={14} />}
            {t.type === 'error' && <AlertCircle size={14} />}
            {t.type === 'info' && <Info size={14} />}
            {t.message}
          </div>
        ))}
      </div>

      {/* Keyframe injection (for spinner) */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ─── Inline Styles ────────────────────────────
// (与 SynonymManager.tsx 风格一致，深色主题)

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex', flexDirection: 'column', height: '100%',
    background: '#0f172a', color: '#e2e8f0', fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
  },
  toolbar: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '10px 16px', background: '#1e293b', borderBottom: '1px solid #334155',
    flexShrink: 0, gap: 12,
  },
  toolbarLeft: { display: 'flex', alignItems: 'center', gap: 16 },
  toolbarRight: { display: 'flex', alignItems: 'center', gap: 8 },
  title: {
    fontSize: 16, fontWeight: 700, color: '#38bdf8', margin: 0,
    display: 'flex', alignItems: 'center', gap: 6,
  },
  statsRow: { display: 'flex', gap: 14, fontSize: 13, color: '#94a3b8' },
  stat: { whiteSpace: 'nowrap' as const },
  statValue: { color: '#38bdf8' },
  btn: {
    display: 'inline-flex', alignItems: 'center', gap: 4,
    padding: '6px 12px', fontSize: 13, borderRadius: 6, cursor: 'pointer',
    background: '#334155', color: '#e2e8f0', border: '1px solid #475569',
  },
  btnActive: { background: '#0ea5e9', borderColor: '#0ea5e9', color: '#fff' },
  btnPrimary: {
    display: 'inline-flex', alignItems: 'center', gap: 4,
    padding: '6px 14px', fontSize: 13, borderRadius: 6, cursor: 'pointer',
    background: '#0ea5e9', color: '#fff', border: '1px solid #0ea5e9',
  },
  main: { display: 'flex', flex: 1, overflow: 'hidden' },
  viewerWrap: { flex: 1, position: 'relative' as const },
  iframe: { width: '100%', height: '100%', border: 'none' },

  // Version panel
  versionPanel: {
    width: 340, minWidth: 340, background: '#1e293b',
    borderLeft: '1px solid #334155', display: 'flex', flexDirection: 'column' as const,
    overflow: 'hidden',
  },
  vPanelHeader: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '12px 16px', borderBottom: '1px solid #334155',
  },
  vPanelTitle: { fontSize: 14, fontWeight: 600, color: '#e2e8f0', margin: 0 },
  closeBtn: {
    background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer',
    padding: '2px 6px', borderRadius: 4,
  },
  versionList: { flex: 1, overflowY: 'auto' as const, padding: 8 },
  versionCard: {
    background: '#0f172a', border: '1px solid #334155', borderRadius: 8,
    padding: 12, marginBottom: 8, transition: 'all .15s',
  },
  versionCardActive: { borderColor: '#0ea5e9', background: '#0c1a30' },
  vCardHeader: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4,
  },
  vNum: { fontSize: 14, fontWeight: 600, color: '#38bdf8' },
  badge: {
    fontSize: 10, padding: '2px 6px', borderRadius: 10,
    background: '#334155', color: '#94a3b8',
  },
  badgeCurrent: {
    fontSize: 10, padding: '2px 6px', borderRadius: 10,
    background: '#065f46', color: '#34d399',
  },
  vMsg: { fontSize: 12, color: '#cbd5e1', marginBottom: 4 },
  vMeta: {
    fontSize: 11, color: '#64748b', display: 'flex', gap: 10,
    alignItems: 'center', flexWrap: 'wrap' as const,
  },
  vActions: { display: 'flex', gap: 6, marginTop: 8 },
  btnSm: {
    display: 'inline-flex', alignItems: 'center', gap: 3,
    padding: '3px 8px', fontSize: 11, borderRadius: 4, cursor: 'pointer',
    background: '#334155', color: '#e2e8f0', border: '1px solid #475569',
  },
  btnSmDanger: { background: '#7f1d1d', borderColor: '#991b1b', color: '#fca5a5' },
  centerText: {
    display: 'flex', flexDirection: 'column' as const, alignItems: 'center',
    gap: 8, padding: '32px 0', color: '#475569', fontSize: 13,
    textAlign: 'center' as const,
  },

  // Upload modal
  overlay: {
    position: 'fixed' as const, inset: 0, background: 'rgba(15,23,42,.85)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 300,
  },
  modal: {
    background: '#1e293b', border: '1px solid #475569', borderRadius: 12,
    padding: 24, width: 460, maxWidth: '90vw',
  },
  modalTitle: {
    fontSize: 16, fontWeight: 600, color: '#e2e8f0', margin: '0 0 16px',
    display: 'flex', alignItems: 'center', gap: 8,
  },
  dropZone: {
    border: '2px dashed #475569', borderRadius: 8, padding: 28,
    textAlign: 'center' as const, cursor: 'pointer',
    display: 'flex', flexDirection: 'column' as const, alignItems: 'center', gap: 8,
    marginBottom: 16, transition: 'all .15s',
  },
  dropText: { fontSize: 13, color: '#94a3b8' },
  dropFileName: { fontSize: 14, color: '#38bdf8', fontWeight: 600 },
  dropFileSize: { fontSize: 12, color: '#64748b' },
  formGroup: { marginBottom: 16 },
  label: { display: 'block', fontSize: 13, color: '#94a3b8', marginBottom: 6 },
  textarea: {
    width: '100%', padding: '8px 12px', background: '#0f172a',
    border: '1px solid #334155', borderRadius: 6, color: '#e2e8f0',
    fontSize: 13, outline: 'none', resize: 'vertical' as const,
    minHeight: 60, fontFamily: 'inherit',
  },
  modalBtnRow: { display: 'flex', gap: 10, justifyContent: 'flex-end' },

  // Toasts
  toastContainer: {
    position: 'fixed' as const, top: 60, right: 20, zIndex: 400,
    display: 'flex', flexDirection: 'column' as const, gap: 8,
  },
  toast: {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '8px 14px', borderRadius: 8, fontSize: 13, minWidth: 220,
    animation: 'toastIn .3s ease',
  },
  toast_success: { background: '#065f46', color: '#34d399', border: '1px solid #047857' },
  toast_error: { background: '#7f1d1d', color: '#fca5a5', border: '1px solid #991b1b' },
  toast_info: { background: '#1e3a5f', color: '#93c5fd', border: '1px solid #1e40af' },
};
