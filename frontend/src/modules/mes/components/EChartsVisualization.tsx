import React from 'react';
import ReactECharts from 'echarts-for-react';
import { ECharts as EChartsType } from 'echarts';
import { TrendingUp, TrendingDown, Minus, Table as TableIcon } from 'lucide-react';

interface EChartsVisualizationProps {
  data: any[];
  type: 'table' | 'bar' | 'line' | 'pie' | 'scatter' | 'card' | 'gauge' | 'table' | 'heatmap' | 'radar' | 'funnel' | 'treemap' | 'boxplot' | 'bar-line-combo' | 'grouped_bar'; // 更新类型
  title?: string;
  xAxisField?: string;
  yAxisField?: string;
  seriesField?: string;  // 分组系列字段（用于 grouped_bar）
  colorField?: string;

  // Card specific
  cardTheme?: 'success' | 'warning' | 'danger' | 'info';
  trend?: { direction: 'up' | 'down' | 'stable'; value: number };
  comparisonValue?: { label: string; value: number };

  // Gauge specific
  gaugeMin?: number;
  gaugeMax?: number;
  gaugeThresholds?: number[];

  // Heatmap specific
  valueField?: string;

  // Alert baselines — injected by response_builder
  thresholds?: Array<{ value: number; level: string; label: string; color?: string }>;
  thresholdDirection?: 'above' | 'below';

  // General
  height?: number | string;
}

export const EChartsVisualization = React.memo(
  ({
    data,
    type,
    title,
    xAxisField,
    yAxisField,
    seriesField,
    colorField,
    cardTheme = 'info',
    trend,
    comparisonValue,
    gaugeMin = 0,
    gaugeMax = 100,
    gaugeThresholds = [70, 85, 95],
    valueField,
    thresholds,
    thresholdDirection = 'below',
    height
  }: EChartsVisualizationProps) => {
    // --- 所有 Hooks 必须在组件函数的最顶层无条件调用 ---

    const echartsRef = React.useRef<EChartsType | null>(null);

    // 使用 useCallback 确保函数引用稳定
    const handleResize = React.useCallback(() => {
      echartsRef.current?.resize();
    }, []); // echartsRef 是一个稳定的引用，所以这里不需要作为依赖

    // 使用 useCallback 确保函数引用稳定
    const handleChartReady = React.useCallback((echart: EChartsType) => {
      echartsRef.current = echart;
      window.addEventListener('resize', handleResize);
    }, [handleResize]); // 依赖 handleResize

    // 使用 useEffect 管理副作用：添加和移除 resize 事件监听器
    React.useEffect(() => {
      // 在这里添加事件监听器，确保它只在组件挂载时添加一次，并在卸载时移除
      // 注意：onChartReady 已经添加了监听器，这里是为了确保即使没有 chartReady 事件，resize 也能工作
      // 并且确保在组件卸载时移除监听器
      window.addEventListener('resize', handleResize);
      return () => {
        window.removeEventListener('resize', handleResize);
      };
    }, [handleResize]); // 依赖 handleResize

    // 使用 useMemo 缓存图表配置
    const generateChartOptions = React.useMemo(() => {
      if (!data || data.length === 0) {
        return {
          title: { text: '暂无数据', left: 'center', top: 'center' }
        };
      }

      const colors = ['#10b981', '#eab308', '#ef4444', '#3b82f6', '#f97316', '#06b6d4'];

      switch (type) {
        case 'bar':
          return generateBarChartOptions(data, title, xAxisField, yAxisField, colors, thresholds);
        case 'line':
          return generateLineChartOptions(data, title, xAxisField, yAxisField, colors, thresholds);
        case 'pie':
          return generatePieChartOptions(data, title, yAxisField, colors);
        case 'scatter':
          return generateScatterChartOptions(data, title, xAxisField, yAxisField, colorField, colors);
        case 'gauge':
          return generateGaugeChartOptions(data, title, yAxisField, gaugeMin, gaugeMax, gaugeThresholds);
        case 'heatmap':
          return generateHeatmapChartOptions(data, title, xAxisField, yAxisField, valueField, colors);
        case 'radar':
          return generateRadarChartOptions(data, title, colors);
        case 'funnel':
          return generateFunnelChartOptions(data, title, yAxisField, colors);
        case 'treemap':
          return generateTreemapChartOptions(data, title, yAxisField, colors);
        case 'boxplot': // 新增箱线图
          return generateBoxplotChartOptions(data, title, xAxisField, yAxisField, colors);
        case 'bar-line-combo': // 新增柱状折线组合图
          return generateBarLineComboChartOptions(data, title, xAxisField, yAxisField, colors);
        case 'grouped_bar': // 分组柱状图（二维分组）
          return generateGroupedBarChartOptions(data, title, xAxisField, seriesField, yAxisField, colors);
        default:
          return generateBarChartOptions(data, title, xAxisField, yAxisField, colors, thresholds);
      }
    }, [data, type, title, xAxisField, yAxisField, seriesField, colorField, valueField, gaugeMin, gaugeMax, gaugeThresholds, thresholds, thresholdDirection]);

    // --- 条件渲染在所有 Hooks 调用之后 ---

    if (type === 'card') {
      return (
        <CardVisualization
          data={data}
          title={title}
          theme={cardTheme}
          trend={trend}
          comparisonValue={comparisonValue}
        />
      );
    }

    if (type === 'table') {
      return <DataTable data={data} />;
    }

    return (
      <div className="w-full h-full bg-white rounded-lg border border-gray-200 overflow-hidden">
        <ReactECharts
          ref={echartsRef}
          option={generateChartOptions}
          notMerge={true}
          lazyUpdate={false}
          style={{ width: '100%', height: height || '100%', minHeight: height || '400px' }}
          opts={{ locale: 'ZH' }}
          onChartReady={handleChartReady}
        />
      </div>
    );
  }
);

EChartsVisualization.displayName = 'EChartsVisualization';

function generateBarChartOptions(
  data: any[],
  title: string | undefined,
  xAxisField: string | undefined,
  yAxisField: string | undefined,
  colors: string[],
  thresholds?: Array<{ value: number; level: string; label: string; color?: string }>
) {
  const displayData = data.slice(0, 20);
  const xField = xAxisField || detectField(data, ['name', 'equipment_id', 'shift', 'product_id']);
  const yField = yAxisField || detectField(data, ['oee', 'yield_rate', 'output_qty', 'performance', 'wip_count']);

  const xAxisData = displayData.map((item) => item[xField] || 'N/A');
  const yAxisData = displayData.map((item) => parseFloat(item[yField]) || 0);

  const seriesData = yAxisData.map((value) => ({
    value,
    itemStyle: {
      color:
        value >= 85 ? colors[0] : value >= 70 ? colors[1] : colors[2]
    }
  }));

  // markLine from baselines
  const markLineData = (thresholds || []).map((t) => ({
    yAxis: t.value,
    name: t.label,
    label: { formatter: `${t.label}: {c}`, color: t.color || '#6b7280' },
    lineStyle: { color: t.color || '#6b7280', type: t.level === 'critical' ? 'solid' : 'dashed', width: 2 },
  }));

  return {
    title: {
      text: title || '柱状图',
      textStyle: { fontSize: 14, fontWeight: 'bold' }
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(0, 0, 0, 0.7)',
      textStyle: { color: '#fff' },
      borderColor: '#ccc'
    },
    legend: {
      data: [yField],
      top: 30
    },
    grid: {
      top: 80,
      left: 50,
      right: 30,
      bottom: 50,
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: xAxisData,
      axisLabel: { interval: 0, rotate: 45 },
      axisLine: { lineStyle: { color: '#ddd' } }
    },
    yAxis: {
      type: 'value',
      name: yField,
      axisLine: { lineStyle: { color: '#ddd' } },
      splitLine: { lineStyle: { color: '#f0f0f0' } }
    },
    series: [
      {
        name: yField,
        type: 'bar',
        data: seriesData,
        itemStyle: { borderRadius: [4, 4, 0, 0] },
        label: { show: true, position: 'top', formatter: '{c}' },
        markLine: markLineData.length > 0 ? { silent: false, data: markLineData } : undefined,
      }
    ]
  };
}

// 分组柱状图：X轴=第一分类维度，系列=第二分类维度，Y轴=数值
function generateGroupedBarChartOptions(
  data: any[],
  title: string | undefined,
  xAxisField: string | undefined,
  seriesField: string | undefined,
  yAxisField: string | undefined,
  colors: string[]
) {
  const xField = xAxisField || detectField(data, ['warehouse_name', 'location_name', 'warehouse', 'name']);
  const sField = seriesField || detectField(data, ['material_model_name', 'material_name', 'product_name', 'name']);
  const yField = yAxisField || detectField(data, ['quantity', 'total_qty', 'count', 'value']);

  // 获取 X 轴唯一值（如各仓库）
  const xValues = [...new Set(data.map((d) => String(d[xField] ?? 'N/A')))];
  // 获取 series 唯一值（如各物料）
  const seriesValues = [...new Set(data.map((d) => String(d[sField] ?? 'N/A')))];

  // 建立 (x, series) → value 的查找表
  const lookup: Record<string, Record<string, number>> = {};
  for (const row of data) {
    const x = String(row[xField] ?? 'N/A');
    const s = String(row[sField] ?? 'N/A');
    if (!lookup[x]) lookup[x] = {};
    lookup[x][s] = parseFloat(row[yField]) || 0;
  }

  const series = seriesValues.map((sv, idx) => ({
    name: sv,
    type: 'bar',
    data: xValues.map((xv) => lookup[xv]?.[sv] ?? 0),
    itemStyle: { borderRadius: [4, 4, 0, 0], color: colors[idx % colors.length] },
    label: { show: seriesValues.length <= 5, position: 'top', fontSize: 11, formatter: '{c}' },
  }));

  return {
    title: { text: title || '分组柱状图', textStyle: { fontSize: 14, fontWeight: 'bold' } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: seriesValues, top: 30 },
    grid: { top: 80, left: 50, right: 30, bottom: 60, containLabel: true },
    xAxis: {
      type: 'category',
      data: xValues,
      axisLabel: { interval: 0, rotate: xValues.length > 6 ? 30 : 0 },
    },
    yAxis: {
      type: 'value',
      name: yField,
      splitLine: { lineStyle: { color: '#f0f0f0' } },
    },
    series,
  };
}

function generateLineChartOptions(
  data: any[],
  title: string | undefined,
  xAxisField: string | undefined,
  yAxisField: string | undefined,
  colors: string[],
  thresholds?: Array<{ value: number; level: string; label: string; color?: string }>
) {
  const displayData = data.slice(0, 30);
  const xField = xAxisField || detectField(data, ['timestamp', 'date', 'name', 'equipment_id']);
  const yField = yAxisField || detectField(data, ['oee', 'yield_rate', 'output_qty', 'performance', 'wip_count']);

  const xAxisData = displayData.map((item, idx) => {
    const value = item[xField];
    if (xField.includes('timestamp') || xField.includes('date')) {
      return new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
    }
    return `${value || 'N/A'}`;
  });

  const yAxisData = displayData.map((item) => parseFloat(item[yField]) || 0);

  // markLine from baselines
  const markLineData = (thresholds || []).map((t) => ({
    yAxis: t.value,
    name: t.label,
    label: { formatter: `${t.label}: {c}`, color: t.color || '#6b7280' },
    lineStyle: { color: t.color || '#6b7280', type: t.level === 'critical' ? 'solid' : 'dashed', width: 2 },
  }));

  return {
    title: {
      text: title || '趋势图',
      textStyle: { fontSize: 14, fontWeight: 'bold' }
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(0, 0, 0, 0.7)',
      textStyle: { color: '#fff' },
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: [yField],
      top: 30
    },
    grid: {
      top: 80,
      left: 50,
      right: 30,
      bottom: 50,
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: xAxisData,
      axisLabel: { interval: Math.floor(displayData.length / 10) || 0, rotate: 45 },
      axisLine: { lineStyle: { color: '#ddd' } }
    },
    yAxis: {
      type: 'value',
      name: yField,
      axisLine: { lineStyle: { color: '#ddd' } },
      splitLine: { lineStyle: { color: '#f0f0f0' } }
    },
    series: [
      {
        name: yField,
        type: 'line',
        data: yAxisData,
        smooth: true,
        itemStyle: { color: colors[3] },
        lineStyle: { color: colors[3], width: 2 },
        areaStyle: { color: { type: 'linear', colorStops: [{ offset: 0, color: `${colors[3]}40` }, { offset: 1, color: `${colors[3]}10` }] } },
        emphasis: { focus: 'series' },
        markLine: markLineData.length > 0 ? { silent: false, data: markLineData } : undefined,
      }
    ]
  };
}

function generatePieChartOptions(
  data: any[],
  title: string | undefined,
  yAxisField: string | undefined,
  colors: string[]
) {
  const yField = yAxisField || detectField(data, ['output_qty', 'good_qty', 'defect_qty', 'count']);
  const categoryField = detectField(data, ['name', 'equipment_id', 'status', 'shift']);

  const pieData = data.map((item) => ({
    name: item[categoryField] || 'N/A',
    value: parseFloat(item[yField]) || 0
  }));

  return {
    title: {
      text: title || '饼图',
      textStyle: { fontSize: 14, fontWeight: 'bold' },
      left: 'center'
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(0, 0, 0, 0.7)',
      textStyle: { color: '#fff' },
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      top: 'center',
      data: pieData.map((item) => item.name)
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['60%', '50%'],
        data: pieData,
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
        label: { formatter: '{b}:\n{d}%' },
        emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } }
      }
    ]
  };
}

function generateScatterChartOptions(
  data: any[],
  title: string | undefined,
  xAxisField: string | undefined,
  yAxisField: string | undefined,
  colorField: string | undefined,
  colors: string[]
) {
  const xField = xAxisField || detectField(data, ['timestamp', 'date', 'equipment_id']);
  const yField = yAxisField || detectField(data, ['oee', 'yield_rate', 'output_qty']);
  const cField = colorField || detectField(data, ['status', 'shift', 'equipment_id']);

  const scatterData = data.map((item) => [
    parseFloat(item[xField]) || 0,
    parseFloat(item[yField]) || 0,
    item[cField] || 'N/A'
  ]);

  return {
    title: {
      text: title || '散点图',
      textStyle: { fontSize: 14, fontWeight: 'bold' }
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(0, 0, 0, 0.7)',
      textStyle: { color: '#fff' },
      formatter: (params: any) => {
        if (params.componentSubType === 'scatter') {
          return `X: ${params.value[0].toFixed(2)}<br/>Y: ${params.value[1].toFixed(2)}<br/>分类: ${params.value[2]}`;
        }
        return params.name;
      }
    },
    legend: {
      data: [...new Set(data.map((item) => item[cField] || 'N/A'))],
      top: 30
    },
    grid: {
      top: 80,
      left: 50,
      right: 30,
      bottom: 50,
      containLabel: true
    },
    xAxis: {
      type: 'value',
      name: xField,
      axisLine: { lineStyle: { color: '#ddd' } },
      splitLine: { lineStyle: { color: '#f0f0f0' } }
    },
    yAxis: {
      type: 'value',
      name: yField,
      axisLine: { lineStyle: { color: '#ddd' } },
      splitLine: { lineStyle: { color: '#f0f0f0' } }
    },
    series: [
      {
        type: 'scatter',
        symbolSize: 8,
        data: scatterData,
        itemStyle: { color: colors[3], opacity: 0.8 },
        emphasis: { itemStyle: { color: colors[2], shadowBlur: 10 } }
      }
    ]
  };
}

function detectField(data: any[], possibleFields: string[]): string {
  for (const field of possibleFields) {
    if (data.length > 0 && field in data[0]) {
      return field;
    }
  }
  return Object.keys(data[0] || {})[0] || '';
}

// Card Visualization Component
function CardVisualization({
  data,
  title,
  theme,
  trend,
  comparisonValue
}: {
  data: any[];
  title?: string;
  theme: 'success' | 'warning' | 'danger' | 'info';
  trend?: { direction: 'up' | 'down' | 'stable'; value: number };
  comparisonValue?: { label: string; value: number };
}) {
  // 定义主题颜色映射对象
  const themeColors = {
    success: 'from-green-500 to-green-600',
    warning: 'from-yellow-500 to-yellow-600',
    danger: 'from-red-500 to-red-600',
    info: 'from-blue-500 to-blue-600'
  };

  if (!data || data.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>暂无数据</p>
      </div>
    );
  }

  // Extract the main value from the data and ensure it's a number
  // Use parseFloat for each potential source to ensure it's a number, falling back to 0
  const mainValue = parseFloat(data[0]?.count) || parseFloat(data[0]?.value) || parseFloat(Object.values(data[0])[0]) || 0;

  const displayTitle = title || Object.keys(data[0])[0] || '统计值';

  // Format large numbers
  const formatNumber = (num: number): string => {
    if (num >= 10000) {
      return `${(num / 10000).toFixed(1)}万`;
    }
    if (num >= 1000) {
      return `${(num / 1000).toFixed(1)}k`;
    }
    return num.toFixed(0);
  };

  return (
    <div className={`rounded-lg bg-gradient-to-br ${themeColors[theme]} p-6 text-white shadow-lg`}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="text-sm font-medium opacity-90 mb-2">{displayTitle}</h3>
          <div className="flex items-baseline space-x-2">
            <span className="text-4xl font-bold">{formatNumber(mainValue)}</span>
            {trend && (
              <div className="flex items-center text-sm">
                {trend.direction === 'up' && <TrendingUp className="w-4 h-4 mr-1" />}
                {trend.direction === 'down' && <TrendingDown className="w-4 h-4 mr-1" />}
                {trend.direction === 'stable' && <Minus className="w-4 h-4 mr-1" />}
                <span>{trend.value}%</span>
              </div>
            )}
          </div>
        </div>
      </div>
      {comparisonValue && (
        <div className="mt-4 pt-4 border-t border-white/20">
          <p className="text-xs opacity-75">{comparisonValue.label}</p>
          <p className="text-lg font-semibold">{comparisonValue.value}</p>
        </div>
      )}
    </div>
  );
}

// Gauge Chart Options
function generateGaugeChartOptions(
  data: any[],
  title: string | undefined,
  yAxisField: string | undefined,
  gaugeMin: number,
  gaugeMax: number,
  gaugeThresholds: number[]
): any {
  const yField = yAxisField || detectField(data, ['oee', 'yield_rate', 'performance', 'value', 'rate']);
  const value = parseFloat(data[0]?.[yField]) || 0;

  // Define color ranges based on thresholds
  const colorStops = [
    [gaugeThresholds[0] / gaugeMax, '#ef4444'], // red
    [gaugeThresholds[1] / gaugeMax, '#eab308'], // yellow
    [gaugeThresholds[2] / gaugeMax, '#10b981'], // green
    [1, '#10b981']
  ];

  return {
    title: {
      text: title || '仪表盘',
      textStyle: { fontSize: 14, fontWeight: 'bold' },
      left: 'center'
    },
    tooltip: {
      formatter: '{b}: {c}%'
    },
    series: [
      {
        type: 'gauge',
        min: gaugeMin,
        max: gaugeMax,
        splitNumber: 10,
        radius: '80%',
        center: ['50%', '60%'],
        startAngle: 200,
        endAngle: -20,
        axisLine: {
          lineStyle: {
            width: 25,
            color: colorStops
          }
        },
        pointer: {
          itemStyle: {
            color: 'auto'
          },
          length: '70%',
          width: 6
        },
        axisTick: {
          distance: -25,
          length: 8,
          lineStyle: {
            color: '#fff',
            width: 2
          }
        },
        splitLine: {
          distance: -25,
          length: 15,
          lineStyle: {
            color: '#fff',
            width: 3
          }
        },
        axisLabel: {
          color: 'auto',
          distance: 35,
          fontSize: 12
        },
        detail: {
          valueAnimation: true,
          formatter: '{value}%',
          color: 'auto',
          fontSize: 24,
          offsetCenter: [0, '80%']
        },
        data: [
          {
            value: value,
            name: yField
          }
        ]
      }
    ]
  };
}

// Heatmap Chart Options
function generateHeatmapChartOptions(
  data: any[],
  title: string | undefined,
  xAxisField: string | undefined,
  yAxisField: string | undefined,
  valueField: string | undefined,
  colors: string[]
): any {
  const xField = xAxisField || detectField(data, ['date', 'timestamp', 'equipment_id']);
  const yField = yAxisField || detectField(data, ['shift', 'status', 'equipment_id']);
  const vField = valueField || detectField(data, ['oee', 'yield_rate', 'output_qty', 'value']);

  const xAxisData = [...new Set(data.map((item) => item[xField]))];
  const yAxisData = [...new Set(data.map((item) => item[yField]))];

  const heatmapData = data.map((item) => [
    xAxisData.indexOf(item[xField]),
    yAxisData.indexOf(item[yField]),
    parseFloat(item[vField]) || 0
  ]);

  const maxValue = Math.max(...heatmapData.map((item) => item[2]));
  const minValue = Math.min(...heatmapData.map((item) => item[2]));

  return {
    title: {
      text: title || '热力图',
      textStyle: { fontSize: 14, fontWeight: 'bold' }
    },
    tooltip: {
      position: 'top',
      formatter: (params: any) => {
        return `${yAxisData[params.value[1]]}<br/>${xAxisData[params.value[0]]}<br/>${vField}: ${params.value[2].toFixed(2)}`;
      }
    },
    grid: {
      top: 80,
      left: 100,
      right: 50,
      bottom: 80,
      containLabel: false
    },
    xAxis: {
      type: 'category',
      data: xAxisData,
      splitArea: {
        show: true
      },
      axisLabel: {
        interval: 0,
        rotate: 45
      }
    },
    yAxis: {
      type: 'category',
      data: yAxisData,
      splitArea: {
        show: true
      }
    },
    visualMap: {
      min: minValue,
      max: maxValue,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 10,
      inRange: {
        color: ['#e0f2fe', '#3b82f6', '#1e3a8a']
      }
    },
    series: [
      {
        type: 'heatmap',
        data: heatmapData,
        label: {
          show: true,
          formatter: (params: any) => params.value[2].toFixed(1)
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  };
}

// Radar Chart Options
function generateRadarChartOptions(data: any[], title: string | undefined, colors: string[]): any {
  // Extract fields (exclude non-numeric fields)
  const firstItem = data[0] || {};
  const nameField = detectField(data, ['name', 'equipment_id', 'product_id', 'shift']);
  const numericFields = Object.keys(firstItem).filter(
    (key) => key !== nameField && typeof firstItem[key] === 'number'
  );

  // Create indicator for radar
  const indicator = numericFields.map((field) => ({
    name: field,
    max: Math.max(...data.map((item) => parseFloat(item[field]) || 0)) * 1.2
  }));

  // Create series data
  const seriesData = data.slice(0, 5).map((item) => ({
    name: item[nameField] || 'N/A',
    value: numericFields.map((field) => parseFloat(item[field]) || 0)
  }));

  return {
    title: {
      text: title || '雷达图',
      textStyle: { fontSize: 14, fontWeight: 'bold' }
    },
    tooltip: {
      trigger: 'item'
    },
    legend: {
      data: seriesData.map((item) => item.name),
      top: 30
    },
    radar: {
      indicator: indicator,
      radius: '60%',
      center: ['50%', '55%']
    },
    series: [
      {
        type: 'radar',
        data: seriesData,
        emphasis: {
          lineStyle: {
            width: 3
          }
        }
      }
    ]
  };
}

// Funnel Chart Options
function generateFunnelChartOptions(
  data: any[],
  title: string | undefined,
  yAxisField: string | undefined,
  colors: string[]
): any {
  const yField = yAxisField || detectField(data, ['output_qty', 'good_qty', 'count', 'value']);
  const categoryField = detectField(data, ['name', 'stage', 'step', 'equipment_id']);

  const funnelData = data.map((item) => ({
    name: item[categoryField] || 'N/A',
    value: parseFloat(item[yField]) || 0
  }));

  return {
    title: {
      text: title || '漏斗图',
      textStyle: { fontSize: 14, fontWeight: 'bold' },
      left: 'center'
    },
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      top: 'center',
      data: funnelData.map((item) => item.name)
    },
    series: [
      {
        type: 'funnel',
        left: '25%',
        width: '50%',
        sort: 'descending',
        gap: 2,
        label: {
          show: true,
          position: 'inside',
          formatter: '{b}: {c}'
        },
        labelLine: {
          length: 10,
          lineStyle: {
            width: 1,
            type: 'solid'
          }
        },
        itemStyle: {
          borderColor: '#fff',
          borderWidth: 1
        },
        emphasis: {
          label: {
            fontSize: 16
          }
        },
        data: funnelData
      }
    ]
  };
}

// Treemap Chart Options
function generateTreemapChartOptions(
  data: any[],
  title: string | undefined,
  yAxisField: string | undefined,
  colors: string[]
): any {
  const yField = yAxisField || detectField(data, ['output_qty', 'good_qty', 'count', 'value']);
  const categoryField = detectField(data, ['name', 'equipment_id', 'product_id', 'category']);

  const treemapData = data.map((item) => ({
    name: item[categoryField] || 'N/A',
    value: parseFloat(item[yField]) || 0
  }));

  return {
    title: {
      text: title || '树状图',
      textStyle: { fontSize: 14, fontWeight: 'bold' },
      left: 'center'
    },
    tooltip: {
      formatter: '{b}: {c}'
    },
    series: [
      {
        type: 'treemap',
        data: treemapData,
        roam: false,
        nodeClick: false,
        breadcrumb: {
          show: false
        },
        label: {
          show: true,
          formatter: '{b}\n{c}'
        },
        itemStyle: {
          borderColor: '#fff',
          borderWidth: 2,
          gapWidth: 2
        },
        levels: [
          {
            itemStyle: {
              borderColor: '#777',
              borderWidth: 0,
              gapWidth: 1
            }
          },
          {
            itemStyle: {
              borderColor: '#555',
              borderWidth: 5,
              gapWidth: 1
            },
            emphasis: {
              itemStyle: {
                borderColor: '#333'
              }
            }
          }
        ]
      }
    ]
  };
}

// Data Table Component
function DataTable({ data }: { data: any[] }) {
  if (!data || data.length === 0) return null;

  const columns = Object.keys(data[0]);
  const displayData = data.slice(0, 10);

  const formatColumnName = (key: string): string => {
    const names: Record<string, string> = {
      equipment_id: '设备ID',
      product_id: '产品ID',
      date: '日期',
      shift: '班次',
      oee: 'OEE(%)',
      availability: '可用率(%)',
      performance: '性能率(%)',
      quality: '质量率(%)',
      timestamp: '时间',
      output_qty: '产量',
      good_qty: '良品数',
      defect_qty: '不良数',
      measurement_type: '测量类型',
      measurement_value: '测量值',
      status: '状态',
      yield_rate: '良率(%)',
      total_downtime: '总停机时间(分)',
      downtime_count: '停机次数',
      avg_downtime: '平均停机时间(分)',
      name: '名称',
      count: '记录数',
      pass_count: '合格数',
      total_count: '总数',
      defect_count: '不良数',
      value: '值'
    };
    return names[key] || key;
  };

  const formatValue = (key: string, value: any): string => {
    if (value === null || value === undefined) return '-';

    if (key.includes('timestamp') || key.includes('created_at')) {
      return new Date(value).toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    }

    if (key === 'date') {
      return new Date(value).toLocaleDateString('zh-CN');
    }

    if (typeof value === 'number') {
      return Number.isInteger(value) ? String(value) : value.toFixed(2);
    }

    return String(value);
  };

  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
      <div className="flex items-center space-x-2 px-4 py-2 bg-gray-50 border-b border-gray-200">
        <TableIcon className="w-4 h-4 text-gray-600" />
        <span className="text-sm font-semibold text-gray-700">数据详情</span>
        <span className="text-xs text-gray-500">({displayData.length} / {data.length} 条)</span>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {columns.map((column) => (
                <th
                  key={column}
                  className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {formatColumnName(column)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {displayData.map((row, idx) => (
              <tr key={idx} className="hover:bg-gray-50 transition-colors">
                {columns.map((column) => (
                  <td key={column} className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">
                    {formatValue(column, row[column])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.length > 10 && (
        <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 text-xs text-gray-500 text-center">
          仅显示前10条记录，完整数据可导出查看
        </div>
      )}
    </div>
  );
}

// New function for Boxplot chart options
function generateBoxplotChartOptions(
  data: any[],
  title: string | undefined,
  xAxisField: string | undefined,
  yAxisField: string | undefined,
  colors: string[]
) {
  const xField = xAxisField || detectField(data, ['category', 'equipment_id', 'shift']);
  const yField = yAxisField || detectField(data, ['value', 'oee', 'quality']);

  // Prepare data for boxplot: group values by xField
  const groupedData: Record<string, number[]> = {};
  data.forEach(item => {
    const category = item[xField];
    const value = parseFloat(item[yField]);
    if (!isNaN(value)) {
      if (!groupedData[category]) {
        groupedData[category] = [];
      }
      groupedData[category].push(value);
    }
  });

  const categories = Object.keys(groupedData);
  const boxplotData = categories.map(category => {
    const values = groupedData[category].sort((a, b) => a - b);
    if (values.length === 0) return [];
    const q1 = values[Math.floor(values.length * 0.25)];
    const median = values[Math.floor(values.length * 0.5)];
    const q3 = values[Math.floor(values.length * 0.75)];
    const min = values[0];
    const max = values[values.length - 1];
    return [min, q1, median, q3, max];
  });

  return {
    title: {
      text: title || '箱线图',
      textStyle: { fontSize: 14, fontWeight: 'bold' }
    },
    tooltip: {
      trigger: 'item',
      axisPointer: {
        type: 'shadow'
      }
    },
    grid: {
      left: '10%',
      right: '10%',
      bottom: '15%'
    },
    xAxis: {
      type: 'category',
      data: categories,
      boundaryGap: true,
      nameGap: 30,
      splitArea: {
        show: false
      },
      axisLabel: {
        formatter: '{value}',
        rotate: 45
      },
      splitLine: {
        show: false
      }
    },
    yAxis: {
      type: 'value',
      name: yField,
      splitArea: {
        show: true
      }
    },
    series: [
      {
        name: 'Boxplot',
        type: 'boxplot',
        data: boxplotData,
        tooltip: {
          formatter: function (param: any) {
            return [
              '类别 ' + param.name + ': ',
              '最大值: ' + param.data[4],
              'Q3: ' + param.data[3],
              '中位数: ' + param.data[2],
              'Q1: ' + param.data[1],
              '最小值: ' + param.data[0]
            ].join('<br/>');
          }
        }
      }
    ]
  };
}

// New function for Bar-Line Combo chart options
function generateBarLineComboChartOptions(
  data: any[],
  title: string | undefined,
  xAxisField: string | undefined,
  yAxisField: string | undefined, // This will be for the primary bar series
  colors: string[]
) {
  const xField = xAxisField || detectField(data, ['timestamp', 'date', 'name', 'equipment_id']);
  const barYField = yAxisField || detectField(data, ['output_qty', 'good_qty']);
  const lineYField = detectField(data, ['oee', 'yield_rate', 'performance']); // Assuming a second metric for the line

  const xAxisData = data.map((item) => {
    const value = item[xField];
    if (xField.includes('timestamp') || xField.includes('date')) {
      return new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
    }
    return `${value || 'N/A'}`;
  });

  const barData = data.map((item) => parseFloat(item[barYField]) || 0);
  const lineData = data.map((item) => parseFloat(item[lineYField]) || 0);

  return {
    title: {
      text: title || '柱状折线组合图',
      textStyle: { fontSize: 14, fontWeight: 'bold' }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        crossStyle: {
          color: '#999'
        }
      }
    },
    legend: {
      data: [barYField, lineYField],
      top: 30
    },
    xAxis: [
      {
        type: 'category',
        data: xAxisData,
        axisPointer: {
          type: 'shadow'
        },
        axisLabel: { interval: Math.floor(data.length / 10) || 0, rotate: 45 },
      }
    ],
    yAxis: [
      {
        type: 'value',
        name: barYField,
        min: 0,
        axisLabel: {
          formatter: '{value}'
        }
      },
      {
        type: 'value',
        name: lineYField,
        min: 0,
        axisLabel: {
          formatter: '{value}%'
        }
      }
    ],
    series: [
      {
        name: barYField,
        type: 'bar',
        data: barData,
        itemStyle: { color: colors[3] }
      },
      {
        name: lineYField,
        type: 'line',
        yAxisIndex: 1,
        data: lineData,
        itemStyle: { color: colors[0] }
      }
    ]
  };
}