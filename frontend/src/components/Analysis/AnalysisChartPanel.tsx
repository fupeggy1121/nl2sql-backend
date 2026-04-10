/**
 * AnalysisChartPanel — 直接渲染后端输出的 ECharts option，零转换。
 */
import React from 'react';
import ReactECharts from 'echarts-for-react';
import type { PlotlyChartSpec } from '../../services/nl2sqlApi';

interface Props {
  charts: PlotlyChartSpec[];
}

const AnalysisChartPanel: React.FC<Props> = ({ charts }) => {
  if (!charts || charts.length === 0) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 8 }}>
      {charts.map((chart, idx) => {
        // 兴容两种后端格式：{ option } (metric_compute) 与 { echarts } (旧格式)
        const echartsOption = chart.option ?? chart.echarts;
        return echartsOption ? (
          <div
            key={idx}
            style={{
              background: '#12142a',
              border: '1px solid #2d284e',
              borderRadius: 8,
              padding: '12px 8px 8px',
            }}
          >
            <ReactECharts
              option={{
                title: chart.title
                  ? { text: chart.title, left: 'center', textStyle: { fontSize: 13 } }
                  : undefined,
                ...echartsOption,
              }}
              style={{ height: 260 }}
              notMerge
              lazyUpdate
            />
          </div>
        ) : (
          <div key={idx} style={{ color: '#9ca3af', fontSize: 13, textAlign: 'center', padding: 16 }}>
            {chart.title ?? '图表暂无数据'}
          </div>
        );
      })}
    </div>
  );
};

export default AnalysisChartPanel;
