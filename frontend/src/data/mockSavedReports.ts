// src/data/mockSavedReports.ts
import {
  Sparkles as SparklesIcon,
  BarChart as BarChartIcon,
  TrendingUp as TrendingUpIcon,
  AlertTriangle as AlertTriangleIcon,
  ClipboardList as ClipboardListIcon,
} from 'lucide-react';
import React from 'react';

export interface SavedReport {
  id: string;
  name: string;
  type: 'mes-chat' | 'generic-report' | 'oee-report' | 'quality-report' | 'downtime-report' | 'production-summary-report';
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  description?: string;
  queryParams?: Record<string, any>;
  sqlQuery?: string;
  data?: any[];
  visualizationType?: 'bar' | 'line' | 'pie' | 'scatter' | 'card' | 'gauge' | 'table' | 'heatmap' | 'radar' | 'funnel' | 'treemap';
  chartConfig?: {
    title?: string;
    xAxisField?: string;
    yAxisField?: string;
    colorField?: string;
    valueField?: string;
    cardTheme?: 'success' | 'warning' | 'danger' | 'info';
    trend?: { direction: 'up' | 'down' | 'stable'; value: number };
    comparisonValue?: { label: string; value: number };
    gaugeMin?: number;
    gaugeMax?: number;
    gaugeThresholds?: number[];
  };
  created_by?: string;
  created_at?: Date;
  updated_at?: Date;
}

// 将 Lucide Icons 作为 SavedReport 的静态属性导出
export namespace SavedReport {
  export const Sparkles = SparklesIcon;
  export const BarChart = BarChartIcon;
  export const TrendingUp = TrendingUpIcon;
  export const AlertTriangle = AlertTriangleIcon;
  export const ClipboardList = ClipboardListIcon;
}
