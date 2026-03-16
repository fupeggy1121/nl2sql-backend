/**
 * OntologyViewer.tsx — 本体可视化 & TTL 版本管理 React 组件
 *
 * 用于 Bolt.new 前端集成。
 *
 * 功能：
 *   - D3 力导向图渲染本体（纯 JSON 数据，无 iframe）
 *   - 节点搜索 / 类型筛选
 *   - 版本历史面板（查看 / 回滚）
 *   - TTL 文件上传弹窗
 *   - 一键刷新 / 热重载
 *
 * 依赖: lucide-react, d3 (需要安装: npm i d3 @types/d3)
 *
 * 使用方式:
 *   import OntologyViewer from './OntologyViewer';
 *   <OntologyViewer />
 */
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  Upload, RefreshCw, History, RotateCcw, Eye, X,
  FileText, Clock, User, HardDrive, Search,
  AlertCircle, CheckCircle, Info, Loader2
} from 'lucide-react';
import { ontologyApi } from '../services/ontologyApi';
import * as d3 from 'd3';

// ─── Types ────────────────────────────────────

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  comment: string;
  type: 'class' | 'dataProperty';
  group: string;
  rangeType?: string;
  virtual?: boolean;
  virtual_kind?: string;
  // physical mapping
  physical_table?: string;
  primary_key?: string;
  key_columns?: string[];
  properties?: Record<string, string>;
}

interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
  label: string;
  uri?: string;
  type: 'objectProperty' | 'dataPropertyEdge' | 'subClassOf';
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
  stats: { classes: number; relations: number; data_properties: number };
}

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

// ─── Color palette for groups ─────────────────
const GROUP_COLORS: Record<string, string> = {};
const PALETTE = [
  '#38bdf8', '#f472b6', '#a78bfa', '#34d399', '#fbbf24',
  '#fb923c', '#f87171', '#818cf8', '#22d3ee', '#a3e635',
  '#c084fc', '#2dd4bf', '#e879f9', '#60a5fa',
];
let colorIdx = 0;
function getGroupColor(group: string): string {
  if (!GROUP_COLORS[group]) {
    GROUP_COLORS[group] = PALETTE[colorIdx % PALETTE.length];
    colorIdx++;
  }
  return GROUP_COLORS[group];
}

// ─── Main Component ───────────────────────────

export default function OntologyViewer() {
  const svgRef = useRef<SVGSVGElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const simulationRef = useRef<d3.Simulation<GraphNode, GraphLink> | null>(null);
  // D3 selection refs for highlight effect
  const nodeSelRef = useRef<d3.Selection<SVGGElement, GraphNode, SVGGElement, unknown> | null>(null);
  const linkSelRef = useRef<d3.Selection<SVGLineElement, GraphLink, SVGGElement, unknown> | null>(null);
  const linkLabelSelRef = useRef<d3.Selection<SVGTextElement, GraphLink, SVGGElement, unknown> | null>(null);
  const linksDataRef = useRef<GraphLink[]>([]);

  // State
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [showDataProps, setShowDataProps] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [showVersionPanel, setShowVersionPanel] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [versions, setVersions] = useState<Version[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadMessage, setUploadMessage] = useState('');
  const [toasts, setToasts] = useState<Toast[]>([]);

  // ─── Toast ──────────────────────────────────
  const addToast = useCallback((message: string, type: Toast['type'] = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  }, []);

  // ─── Load graph data ───────────────────────
  const loadGraph = useCallback(async () => {
    setGraphLoading(true);
    setGraphError(null);
    try {
      const data = await ontologyApi.getGraph();
      setGraphData(data);
    } catch (e: any) {
      setGraphError(e.message);
      console.error('Load graph failed:', e);
    } finally {
      setGraphLoading(false);
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

  useEffect(() => { loadGraph(); }, [loadGraph]);

  useEffect(() => {
    if (showVersionPanel) loadVersions();
  }, [showVersionPanel, loadVersions]);

  // ─── Filtered data ─────────────────────────
  const filteredData = useMemo(() => {
    if (!graphData) return null;
    let nodes = graphData.nodes;
    let links = graphData.links;

    // 过滤数据属性
    if (!showDataProps) {
      nodes = nodes.filter(n => n.type !== 'dataProperty');
      links = links.filter(l => l.type !== 'dataPropertyEdge');
    }

    // 搜索高亮（不过滤节点，只标记）
    return { nodes, links, stats: graphData.stats };
  }, [graphData, showDataProps]);

  // ─── D3 Force Graph ────────────────────────
  useEffect(() => {
    if (!filteredData || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth || 900;
    const height = svgRef.current.clientHeight || 600;

    // Clear previous
    svg.selectAll('*').remove();
    // Reset selection refs to avoid stale highlight effect
    nodeSelRef.current = null;
    linkSelRef.current = null;
    linkLabelSelRef.current = null;
    linksDataRef.current = [];

    // Deep copy to avoid D3 mutating state
    const nodes: GraphNode[] = filteredData.nodes.map(n => ({ ...n }));
    const links: GraphLink[] = filteredData.links.map(l => ({ ...l }));

    // Container with zoom
    const g = svg.append('g');
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => g.attr('transform', event.transform));
    svg.call(zoom);

    // Arrow marker
    svg.append('defs').selectAll('marker')
      .data(['arrow'])
      .join('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 25)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#475569');

    // Simulation
    const simulation = d3.forceSimulation<GraphNode>(nodes)
      .force('link', d3.forceLink<GraphNode, GraphLink>(links).id(d => d.id).distance(120))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide<GraphNode>().radius(d => d.virtual ? 36 : 30));

    simulationRef.current = simulation;

    // Links
    const link = g.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', d => {
        if (d.type === 'subClassOf') return '#7c3aed';      // 紫色 — 继承关系
        if (d.type === 'objectProperty') return '#475569';
        return '#334155';
      })
      .attr('stroke-width', d => d.type === 'subClassOf' ? 1.5 : d.type === 'objectProperty' ? 1.5 : 1)
      .attr('stroke-dasharray', d => d.type === 'dataPropertyEdge' ? '4,3' : 'none')
      .attr('marker-end', 'url(#arrow)');

    // Link labels
    const linkLabel = g.append('g')
      .selectAll('text')
      .data(links)
      .join('text')
      .text(d => d.label)
      .attr('font-size', 9)
      .attr('fill', '#64748b')
      .attr('text-anchor', 'middle')
      .style('pointer-events', 'none');

    // Nodes
    const node = g.append('g')
      .selectAll<SVGGElement, GraphNode>('g')
      .data(nodes)
      .join('g')
      .call(d3.drag<SVGGElement, GraphNode>()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on('drag', (event, d) => {
          d.fx = event.x; d.fy = event.y;
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null; d.fy = null;
        })
      )
      .on('click', (_event, d) => setSelectedNode(prev => prev?.id === d.id ? null : d));

    // diamond path helper (for virtual type-template classes)
    const diamondPath = (r: number) =>
      `M0,${-r} L${r},0 L0,${r} L${-r},0 Z`;

    // hexagon path helper (for virtual action/event classes)
    const hexPath = (r: number) => {
      const h = +(r * 0.866).toFixed(2);
      const h2 = +(r * 0.5).toFixed(2);
      return `M0,${-r} L${h},${-h2} L${h},${h2} L0,${r} L${-h},${h2} L${-h},${-h2} Z`;
    };

    // ── Virtual type-template class nodes: diamond shape ──
    node.filter(d => d.type === 'class' && !!d.virtual && d.virtual_kind !== 'action_event' && d.virtual_kind !== 'EmbeddedJSON')
      .append('path')
      .attr('d', diamondPath(20))
      .attr('fill', '#1c1408')
      .attr('stroke', d => {
        if (searchTerm && d.label.toLowerCase().includes(searchTerm.toLowerCase())) return '#fbbf24';
        return '#f59e0b';
      })
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', '5,3')
      .attr('opacity', 0.92);

    // "T" label inside diamond
    node.filter(d => d.type === 'class' && !!d.virtual && d.virtual_kind !== 'action_event' && d.virtual_kind !== 'EmbeddedJSON')
      .append('text')
      .text('T')
      .attr('dy', '0.35em')
      .attr('text-anchor', 'middle')
      .attr('font-size', 10)
      .attr('font-weight', 700)
      .attr('fill', '#fbbf24')
      .style('pointer-events', 'none');

    // ── Virtual action/event class nodes: hexagon shape ──
    node.filter(d => d.type === 'class' && !!d.virtual && d.virtual_kind === 'action_event')
      .append('path')
      .attr('d', hexPath(20))
      .attr('fill', '#120c1e')
      .attr('stroke', d => {
        if (searchTerm && d.label.toLowerCase().includes(searchTerm.toLowerCase())) return '#c4b5fd';
        return '#8b5cf6';
      })
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', '5,3')
      .attr('opacity', 0.92);

    // "A" label inside hexagon
    node.filter(d => d.type === 'class' && !!d.virtual && d.virtual_kind === 'action_event')
      .append('text')
      .text('A')
      .attr('dy', '0.35em')
      .attr('text-anchor', 'middle')
      .attr('font-size', 10)
      .attr('font-weight', 700)
      .attr('fill', '#c4b5fd')
      .style('pointer-events', 'none');

    // ── Regular class nodes: circle ──
    node.filter(d => d.type === 'class' && (!d.virtual || d.virtual_kind === 'EmbeddedJSON'))
      .append('circle')
      .attr('r', 18)
      .attr('fill', d => getGroupColor(d.group))
      .attr('stroke', d => {
        if (searchTerm && d.label.toLowerCase().includes(searchTerm.toLowerCase())) return '#fbbf24';
        return '#1e293b';
      })
      .attr('stroke-width', d =>
        searchTerm && d.label.toLowerCase().includes(searchTerm.toLowerCase()) ? 3 : 2
      )
      .attr('opacity', 0.9);

    // ── DataProperty nodes: circle ──
    node.filter(d => d.type === 'dataProperty')
      .append('circle')
      .attr('r', 10)
      .attr('fill', '#334155')
      .attr('stroke', '#475569')
      .attr('stroke-width', 2)
      .attr('opacity', 0.7);

    // Node labels (below node)
    node.append('text')
      .text(d => d.label.length > 12 ? d.label.slice(0, 12) + '…' : d.label)
      .attr('dy', d => {
        if (d.type === 'dataProperty') return 20;
        if (d.virtual && d.virtual_kind !== 'EmbeddedJSON') return 32;
        return 30;
      })
      .attr('text-anchor', 'middle')
      .attr('font-size', d => d.type === 'class' ? 11 : 9)
      .attr('fill', d => {
        if (d.virtual && d.virtual_kind === 'action_event') return '#c4b5fd';
        if (d.virtual && d.virtual_kind !== 'EmbeddedJSON') return '#fde68a';
        if (d.type === 'class') return '#e2e8f0';
        return '#94a3b8';
      })
      .style('pointer-events', 'none');

    // Save selections to refs for highlight effect
    nodeSelRef.current = node as unknown as d3.Selection<SVGGElement, GraphNode, SVGGElement, unknown>;
    linkSelRef.current = link as unknown as d3.Selection<SVGLineElement, GraphLink, SVGGElement, unknown>;
    linkLabelSelRef.current = linkLabel as unknown as d3.Selection<SVGTextElement, GraphLink, SVGGElement, unknown>;
    linksDataRef.current = links;

    // Tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as GraphNode).x!)
        .attr('y1', d => (d.source as GraphNode).y!)
        .attr('x2', d => (d.target as GraphNode).x!)
        .attr('y2', d => (d.target as GraphNode).y!);

      linkLabel
        .attr('x', d => ((d.source as GraphNode).x! + (d.target as GraphNode).x!) / 2)
        .attr('y', d => ((d.source as GraphNode).y! + (d.target as GraphNode).y!) / 2 - 4);

      node.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    // Fit to view after stabilization
    simulation.on('end', () => {
      const bounds = (g.node() as SVGGElement)?.getBBox();
      if (bounds && bounds.width > 0) {
        const scale = Math.min(
          width / (bounds.width + 80),
          height / (bounds.height + 80),
          1.5
        );
        const tx = width / 2 - (bounds.x + bounds.width / 2) * scale;
        const ty = height / 2 - (bounds.y + bounds.height / 2) * scale;
        svg.transition().duration(500)
          .call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
      }
    });

    return () => { simulation.stop(); };
  }, [filteredData, searchTerm]);

  // ─── Highlight selected node 1-hop neighbors ──
  useEffect(() => {
    const node = nodeSelRef.current;
    const link = linkSelRef.current;
    const linkLabel = linkLabelSelRef.current;
    if (!node || !link) return;

    if (!selectedNode) {
      // Reset all to default opacity
      node.attr('opacity', d => d.type === 'dataProperty' ? 0.7 : 0.9);
      link.attr('opacity', 1);
      if (linkLabel) linkLabel.attr('opacity', 1);
      return;
    }

    // Compute 1-hop neighbor IDs
    const neighborIds = new Set<string>([selectedNode.id]);
    linksDataRef.current.forEach(l => {
      const srcId = typeof l.source === 'object' ? (l.source as GraphNode).id : l.source as string;
      const tgtId = typeof l.target === 'object' ? (l.target as GraphNode).id : l.target as string;
      if (srcId === selectedNode.id) neighborIds.add(tgtId);
      if (tgtId === selectedNode.id) neighborIds.add(srcId);
    });

    // Dim non-neighbor nodes
    node.attr('opacity', d => neighborIds.has(d.id) ? (d.type === 'dataProperty' ? 0.9 : 1.0) : 0.08);

    // Dim non-adjacent links
    link.attr('opacity', d => {
      const srcId = typeof d.source === 'object' ? (d.source as GraphNode).id : d.source as string;
      const tgtId = typeof d.target === 'object' ? (d.target as GraphNode).id : d.target as string;
      return (srcId === selectedNode.id || tgtId === selectedNode.id) ? 1 : 0.05;
    });

    if (linkLabel) {
      linkLabel.attr('opacity', d => {
        const srcId = typeof d.source === 'object' ? (d.source as GraphNode).id : d.source as string;
        const tgtId = typeof d.target === 'object' ? (d.target as GraphNode).id : d.target as string;
        return (srcId === selectedNode.id || tgtId === selectedNode.id) ? 1 : 0.05;
      });
    }

    // Highlight selected node shape (add ring)
    node.each(function(d) {
      const g = d3.select<SVGGElement, GraphNode>(this);
      g.select('.selected-ring').remove();
      if (d.id === selectedNode.id) {
        g.insert('circle', ':first-child')
          .attr('class', 'selected-ring')
          .attr('r', d.type === 'dataProperty' ? 14 : (d.virtual && d.virtual_kind !== 'EmbeddedJSON') ? 26 : 23)
          .attr('fill', 'none')
          .attr('stroke', '#f59e0b')
          .attr('stroke-width', 3)
          .attr('stroke-dasharray', 'none');
      }
    });
  }, [selectedNode]);

  // ─── Actions ────────────────────────────────
  const handleReload = useCallback(async () => {
    try {
      await ontologyApi.reload();
      await loadGraph();
      addToast('热重载完成', 'success');
    } catch (e: any) {
      addToast('热重载失败: ' + e.message, 'error');
    }
  }, [loadGraph, addToast]);

  const handleUpload = useCallback(async () => {
    if (!uploadFile) return;
    setUploading(true);
    try {
      const data = await ontologyApi.uploadTTL(uploadFile, uploadMessage);
      addToast(data.message || `已保存为 v${data.version?.version}`, 'success');
      setShowUploadModal(false);
      setUploadFile(null);
      setUploadMessage('');
      await loadGraph();
      if (showVersionPanel) loadVersions();
    } catch (e: any) {
      addToast('上传失败: ' + e.message, 'error');
    } finally {
      setUploading(false);
    }
  }, [uploadFile, uploadMessage, loadGraph, showVersionPanel, loadVersions, addToast]);

  const handleRollback = useCallback(async (version: number) => {
    if (!confirm(`确定回滚到版本 v${version}？\n将创建新版本记录并恢复历史内容。`)) return;
    try {
      const data = await ontologyApi.rollback(version);
      addToast(data.message || `已回滚到 v${version}`, 'success');
      await loadGraph();
      loadVersions();
    } catch (e: any) {
      addToast('回滚失败: ' + e.message, 'error');
    }
  }, [loadGraph, loadVersions, addToast]);

  const handleViewVersion = useCallback(async (version: number) => {
    try {
      const data = await ontologyApi.getVersion(version);
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
          {graphData?.stats && (
            <div style={styles.statsRow}>
              <span style={styles.stat}>
                类: <b style={styles.statValue}>{graphData.stats.classes}</b>
              </span>
              <span style={styles.stat}>
                关系: <b style={styles.statValue}>{graphData.stats.relations}</b>
              </span>
              <span style={styles.stat}>
                数据属性: <b style={styles.statValue}>{graphData.stats.data_properties}</b>
              </span>
            </div>
          )}
        </div>
        <div style={styles.toolbarRight}>
          {/* Search */}
          <div style={styles.searchWrap}>
            <Search size={13} style={{ color: '#64748b' }} />
            <input
              style={styles.searchInput}
              placeholder="搜索节点..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
            />
          </div>
          <label style={styles.toggleLabel}>
            <input
              type="checkbox"
              checked={showDataProps}
              onChange={e => setShowDataProps(e.target.checked)}
              style={{ marginRight: 4 }}
            />
            数据属性
          </label>
          {/* Legend */}
          <div style={styles.legendWrap}>
            <span style={styles.legendItem}>
              <svg width="14" height="14" style={{ marginRight: 4 }}>
                <circle cx="7" cy="7" r="6" fill="#38bdf8" stroke="#1e293b" strokeWidth="1.5" />
              </svg>
              实体类
            </span>
            <span style={styles.legendItem}>
              <svg width="14" height="14" style={{ marginRight: 4 }}>
                <path d="M7,1 L13,7 L7,13 L1,7 Z" fill="#1c1408" stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="3,2" />
              </svg>
              类型模板
            </span>
            <span style={styles.legendItem}>
              <svg width="14" height="14" style={{ marginRight: 4 }}>
                <path d="M7,1 L12.2,4 L12.2,10 L7,13 L1.8,10 L1.8,4 Z" fill="#120c1e" stroke="#8b5cf6" strokeWidth="1.5" strokeDasharray="3,2" />
              </svg>
              操作/事件类
            </span>
          </div>
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
        {/* Graph area */}
        <div style={styles.viewerWrap}>
          {graphLoading && (
            <div style={styles.loadingOverlay}>
              <Loader2 size={28} style={{ animation: 'spin 1s linear infinite' }} />
              <span>加载图数据...</span>
            </div>
          )}
          {graphError && (
            <div style={styles.errorOverlay}>
              <AlertCircle size={24} color="#fca5a5" />
              <div style={{ maxWidth: 500, wordBreak: 'break-word' as const }}>
                <b>连接后端失败</b>
                <p style={{ fontSize: 12, marginTop: 8, color: '#94a3b8', whiteSpace: 'pre-wrap' as const }}>
                  {graphError}
                </p>
                <button style={{ ...styles.btn, marginTop: 12 }} onClick={loadGraph}>
                  <RefreshCw size={14} /> 重试
                </button>
              </div>
            </div>
          )}
          <svg ref={svgRef} style={styles.svg} />

          {/* Node detail panel */}
          {selectedNode && (() => {
            // Compute connected links for this node
            const allLinks = filteredData?.links ?? [];
            const allNodes = filteredData?.nodes ?? [];
            const nodeById = Object.fromEntries(allNodes.map(n => [n.id, n]));

            // Object properties: outgoing (this node as domain)
            const outObjectProps = allLinks.filter(
              l => l.type === 'objectProperty' && (l.source as GraphNode).id === selectedNode.id
            );
            // Object properties: incoming (this node as range)
            const inObjectProps = allLinks.filter(
              l => l.type === 'objectProperty' && (l.target as GraphNode).id === selectedNode.id
            );
            // Data properties attached to this node
            const dataProps = allLinks.filter(
              l => l.type === 'dataPropertyEdge' && (l.source as GraphNode).id === selectedNode.id
            );

            return (
              <div style={styles.detailPanel}>
                <div style={styles.detailHeader}>
                  <span style={styles.detailTitle}>{selectedNode.label}</span>
                  <button style={styles.closeBtn} onClick={() => setSelectedNode(null)}>
                    <X size={14} />
                  </button>
                </div>
                <div style={styles.detailBody}>
                  {/* URI */}
                  <div style={styles.detailRow}>
                    <span style={styles.detailLabel}>URI</span>
                    <span style={{ ...styles.detailValue, fontFamily: 'monospace', fontSize: 11 }}>{selectedNode.id}</span>
                  </div>

                  {/* 类型 */}
                  <div style={styles.detailRow}>
                    <span style={styles.detailLabel}>类型</span>
                    <span style={styles.detailValue}>
                      {selectedNode.type === 'dataProperty'
                        ? '数据属性'
                        : selectedNode.virtual && selectedNode.virtual_kind === 'action_event'
                          ? '操作/事件类（抽象）'
                          : selectedNode.virtual && selectedNode.virtual_kind !== 'EmbeddedJSON'
                            ? '类型模板（虚拟类）'
                            : '本体类（实体）'}
                    </span>
                  </div>

                  {/* 虚拟类说明 */}
                  {selectedNode.virtual && selectedNode.virtual_kind !== 'EmbeddedJSON' && (
                    <div style={styles.detailRow}>
                      <span style={{ ...styles.detailValue, color: selectedNode.virtual_kind === 'action_event' ? '#c4b5fd' : '#fbbf24', fontSize: 11 }}>
                        {selectedNode.virtual_kind === 'action_event'
                          ? '抽象操作/事件类，定义操作行为规则，无物理表。'
                          : 'Type 层模板，无物理表。执行记录见对应 *Record 实例类。'}
                      </span>
                    </div>
                  )}

                  {/* 描述 */}
                  {selectedNode.comment && (
                    <div style={styles.detailRow}>
                      <span style={styles.detailLabel}>描述</span>
                      <span style={{ ...styles.detailValue, fontSize: 12, color: '#cbd5e1' }}>{selectedNode.comment}</span>
                    </div>
                  )}

                  {/* 数据属性值类型（dataProperty节点本身） */}
                  {selectedNode.rangeType && (
                    <div style={styles.detailRow}>
                      <span style={styles.detailLabel}>值类型</span>
                      <span style={{ ...styles.detailValue, fontFamily: 'monospace', fontSize: 11 }}>{selectedNode.rangeType}</span>
                    </div>
                  )}

                  {/* 分组 */}
                  <div style={styles.detailRow}>
                    <span style={styles.detailLabel}>分组</span>
                    <span style={{ ...styles.detailValue, color: getGroupColor(selectedNode.group) }}>{selectedNode.group}</span>
                  </div>

                  {/* ── 物理映射（仅class节点） ── */}
                  {selectedNode.type === 'class' && selectedNode.physical_table && (
                    <>
                      <div style={styles.sectionDivider} />
                      <div style={styles.sectionTitle}>物理映射</div>
                      <div style={styles.detailRow}>
                        <span style={styles.detailLabel}>物理表</span>
                        <span style={{ ...styles.detailValue, fontFamily: 'monospace', color: '#38bdf8' }}>{selectedNode.physical_table}</span>
                      </div>
                      {selectedNode.primary_key && (
                        <div style={styles.detailRow}>
                          <span style={styles.detailLabel}>主键</span>
                          <span style={{ ...styles.detailValue, fontFamily: 'monospace', fontSize: 11 }}>{selectedNode.primary_key}</span>
                        </div>
                      )}
                      {selectedNode.key_columns && selectedNode.key_columns.length > 0 && (
                        <div style={styles.detailRow}>
                          <span style={styles.detailLabel}>关键列</span>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 2 }}>
                            {selectedNode.key_columns.map(col => (
                              <span key={col} style={styles.colBadge}>{col}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 && (
                        <div style={styles.detailRow}>
                          <span style={styles.detailLabel}>语义属性 → 列映射</span>
                          <div style={{ marginTop: 4 }}>
                            {Object.entries(selectedNode.properties).map(([sem, col]) => (
                              <div key={sem} style={styles.propRow}>
                                <span style={styles.propSem}>{sem.replace('semi:', '')}</span>
                                <span style={styles.propArrow}>→</span>
                                <span style={styles.propCol}>{String(col)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}

                  {/* ── 对象属性（仅class节点） ── */}
                  {selectedNode.type === 'class' && (outObjectProps.length > 0 || inObjectProps.length > 0) && (
                    <>
                      <div style={styles.sectionDivider} />
                      <div style={styles.sectionTitle}>对象属性</div>
                      {outObjectProps.length > 0 && (
                        <div style={styles.detailRow}>
                          <span style={styles.detailLabel}>出边（此类 → 目标）</span>
                          {outObjectProps.map(l => {
                            const tgt = nodeById[(l.target as GraphNode).id];
                            return (
                              <div key={l.uri || l.label} style={styles.relRow}>
                                <span style={styles.relProp}>{l.label}</span>
                                <span style={styles.relArrow}>→</span>
                                <span
                                  style={{ ...styles.relTarget, cursor: 'pointer' }}
                                  onClick={() => tgt && setSelectedNode(tgt)}
                                >{tgt?.label || (l.target as GraphNode).id}</span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                      {inObjectProps.length > 0 && (
                        <div style={styles.detailRow}>
                          <span style={styles.detailLabel}>入边（来源 → 此类）</span>
                          {inObjectProps.map(l => {
                            const src = nodeById[(l.source as GraphNode).id];
                            return (
                              <div key={(l.uri || l.label) + '_in'} style={styles.relRow}>
                                <span
                                  style={{ ...styles.relTarget, cursor: 'pointer' }}
                                  onClick={() => src && setSelectedNode(src)}
                                >{src?.label || (l.source as GraphNode).id}</span>
                                <span style={styles.relArrow}>→</span>
                                <span style={styles.relProp}>{l.label}</span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </>
                  )}

                  {/* ── 数据属性（仅class节点） ── */}
                  {selectedNode.type === 'class' && dataProps.length > 0 && (
                    <>
                      <div style={styles.sectionDivider} />
                      <div style={styles.sectionTitle}>数据属性</div>
                      <div style={styles.detailRow}>
                        {dataProps.map(l => {
                          const dpNode = nodeById[(l.target as GraphNode).id];
                          return (
                            <div key={l.uri || l.label} style={styles.dpRow}>
                              <span style={styles.dpName}>{l.label}</span>
                              {dpNode?.rangeType && (
                                <span style={styles.dpType}>{dpNode.rangeType.replace('xsd:', '')}</span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </>
                  )}
                </div>
              </div>
            );
          })()}
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

            <div style={styles.formGroup}>
              <label style={styles.label}>版本说明</label>
              <textarea
                style={styles.textarea}
                placeholder="描述本次修改内容..."
                value={uploadMessage}
                onChange={e => setUploadMessage(e.target.value)}
              />
            </div>

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
          <div key={t.id} style={{ ...styles.toast, ...(styles as any)[`toast_${t.type}`] }}>
            {t.type === 'success' && <CheckCircle size={14} />}
            {t.type === 'error' && <AlertCircle size={14} />}
            {t.type === 'info' && <Info size={14} />}
            {t.message}
          </div>
        ))}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ─── Inline Styles ────────────────────────────

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex', flexDirection: 'column', height: '100%',
    background: '#0f172a', color: '#e2e8f0', fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
  },
  toolbar: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '10px 16px', background: '#1e293b', borderBottom: '1px solid #334155',
    flexShrink: 0, gap: 12, flexWrap: 'wrap' as const,
  },
  toolbarLeft: { display: 'flex', alignItems: 'center', gap: 16 },
  toolbarRight: { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' as const },
  title: {
    fontSize: 16, fontWeight: 700, color: '#38bdf8', margin: 0,
    display: 'flex', alignItems: 'center', gap: 6,
  },
  statsRow: { display: 'flex', gap: 14, fontSize: 13, color: '#94a3b8' },
  stat: { whiteSpace: 'nowrap' as const },
  statValue: { color: '#38bdf8' },
  searchWrap: {
    display: 'flex', alignItems: 'center', gap: 4,
    padding: '4px 10px', background: '#0f172a', borderRadius: 6,
    border: '1px solid #334155',
  },
  searchInput: {
    background: 'transparent', border: 'none', outline: 'none',
    color: '#e2e8f0', fontSize: 13, width: 120,
  },
  toggleLabel: {
    display: 'flex', alignItems: 'center', fontSize: 12, color: '#94a3b8',
    cursor: 'pointer', whiteSpace: 'nowrap' as const,
  },
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
  viewerWrap: { flex: 1, position: 'relative' as const, overflow: 'hidden' },
  svg: { width: '100%', height: '100%', background: '#0f172a' },
  loadingOverlay: {
    position: 'absolute' as const, inset: 0, display: 'flex',
    flexDirection: 'column' as const, alignItems: 'center', justifyContent: 'center',
    gap: 12, color: '#94a3b8', fontSize: 14, zIndex: 10,
    background: 'rgba(15,23,42,.7)',
  },
  errorOverlay: {
    position: 'absolute' as const, inset: 0, display: 'flex',
    flexDirection: 'column' as const, alignItems: 'center', justifyContent: 'center',
    gap: 12, color: '#fca5a5', fontSize: 14, zIndex: 10,
    background: 'rgba(15,23,42,.9)', textAlign: 'center' as const,
  },

  // Node detail
  detailPanel: {
    position: 'absolute' as const, bottom: 16, left: 16,
    background: '#1e293b', border: '1px solid #334155', borderRadius: 10,
    padding: 0, width: 340, maxWidth: 'calc(100vw - 32px)', zIndex: 20, overflow: 'hidden',
    boxShadow: '0 8px 24px rgba(0,0,0,.4)',
  },
  detailHeader: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '10px 14px', borderBottom: '1px solid #334155',
  },
  detailTitle: { fontSize: 14, fontWeight: 600, color: '#38bdf8' },
  detailBody: { padding: '8px 14px 12px', maxHeight: 420, overflowY: 'auto' as const },
  detailRow: { marginBottom: 8 },
  detailLabel: { fontSize: 11, color: '#64748b', display: 'block', marginBottom: 3 },
  detailValue: { fontSize: 13, color: '#e2e8f0', wordBreak: 'break-all' as const },
  sectionDivider: { height: 1, background: '#334155', margin: '8px 0' },
  sectionTitle: { fontSize: 11, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' as const, letterSpacing: '0.05em', marginBottom: 6 },
  colBadge: { fontSize: 10, padding: '1px 6px', background: '#0f172a', border: '1px solid #334155', borderRadius: 4, color: '#94a3b8', fontFamily: 'monospace' },
  propRow: { display: 'flex', alignItems: 'center', gap: 4, marginBottom: 3 },
  propSem: { fontSize: 11, color: '#a5b4fc', fontFamily: 'monospace', minWidth: 0, flex: '1 1 auto', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const },
  propArrow: { fontSize: 11, color: '#475569', flexShrink: 0 },
  propCol: { fontSize: 11, color: '#38bdf8', fontFamily: 'monospace', minWidth: 0, flex: '1 1 auto', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const },
  relRow: { display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4, flexWrap: 'wrap' as const },
  relProp: { fontSize: 11, color: '#fbbf24', fontFamily: 'monospace' },
  relArrow: { fontSize: 11, color: '#475569' },
  relTarget: { fontSize: 11, color: '#7dd3fc', textDecoration: 'underline' },
  dpRow: { display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 },
  dpName: { fontSize: 12, color: '#c4b5fd' },
  dpType: { fontSize: 10, padding: '1px 5px', background: '#1e1b4b', border: '1px solid #4338ca', borderRadius: 4, color: '#a5b4fc' },

  // Version panel
  versionPanel: {
    width: 320, minWidth: 320, background: '#1e293b',
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
  legendWrap: {
    display: 'flex', alignItems: 'center', gap: 10,
    padding: '3px 10px', background: '#0f172a', borderRadius: 6,
    border: '1px solid #334155',
  },
  legendItem: {
    display: 'flex', alignItems: 'center', fontSize: 11, color: '#94a3b8',
    whiteSpace: 'nowrap' as const,
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
