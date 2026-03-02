// src/components/Reports/ReportsModule.tsx
import React, { useState, useEffect } from 'react';
import { BarChart, TrendingUp, Calendar, Download, Filter, Search, AlertTriangle, ClipboardList, RefreshCw } from 'lucide-react';
import { SavedReport } from '../../data/mockSavedReports';
import { useData } from '../../hooks/useData';
import { EChartsVisualization } from '../../modules/mes/components/EChartsVisualization';
import { nl2sqlApi } from '../../services/nl2sqlApi';

interface ReportsModuleProps {
  reportId?: string;
  queryParams?: Record<string, any>;
}

export const ReportsModule: React.FC<ReportsModuleProps> = ({ reportId, queryParams }) => {
  const { savedReports } = useData();
  const [displayedReportData, setDisplayedReportData] = useState<any[] | undefined>(undefined);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [currentReport, setCurrentReport] = useState<SavedReport | null>(null);

  // Effect to update currentReport and displayedReportData when reportId or savedReports change
  useEffect(() => {
    const foundReport = reportId ? savedReports.find(r => r.id === reportId) : null;
    setCurrentReport(foundReport);
    setDisplayedReportData(foundReport?.data); // Initialize with saved data
  }, [reportId, savedReports]);

  const handleRefresh = async () => {
    if (!currentReport || !currentReport.sqlQuery) {
      alert('此报表没有可执行的SQL查询。');
      return;
    }

    setIsRefreshing(true);
    try {
      // 使用 currentReport.sqlQuery 执行查询并获取最新数据
      const response = await nl2sqlApi.executeApprovedQuery(currentReport.sqlQuery);
      
      if (response.success && response.data) {
        setDisplayedReportData(response.data);
        alert('报表数据已刷新！');
      } else {
        alert(`刷新失败: ${response.error || '未知错误'}`);
      }
    } catch (error) {
      console.error('Error refreshing report:', error);
      alert('刷新报表数据时发生错误。');
    } finally {
      setIsRefreshing(false);
    }
  };

  const renderReportContent = () => {
    if (!currentReport) {
      return (
        <div className="text-center py-12">
          <BarChart className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">请从左侧选择一个报表或视图</h3>
          <p className="mt-1 text-sm text-gray-500">这里将显示您选择的报表内容。</p>
        </div>
      );
    }

    if (currentReport.type === 'mes-chat') {
      return (
        <div className="p-6">
          <h3 className="text-xl font-bold text-gray-900 mb-4">{currentReport.name}</h3>
          <p className="text-gray-600 mb-6">{currentReport.description}</p>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-sm text-blue-800">
              这是一个聊天会话保存的快照。要查看完整的交互历史，请在 MES 聊天界面中打开此会话。
            </p>
          </div>
        </div>
      );
    }

    // Render visualization if data is available
    if (displayedReportData && displayedReportData.length > 0) {
      return (
        <div className="p-6">
          <h3 className="text-xl font-bold text-gray-900 mb-4">{currentReport.name}</h3>
          <p className="text-gray-600 mb-6">{currentReport.description}</p>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <EChartsVisualization
              data={displayedReportData}
              type={currentReport.visualizationType || 'table'}
              title={currentReport.chartConfig?.title}
              xAxisField={currentReport.chartConfig?.xAxisField}
              yAxisField={currentReport.chartConfig?.yAxisField}
              colorField={currentReport.chartConfig?.colorField}
              valueField={currentReport.chartConfig?.valueField}
              cardTheme={currentReport.chartConfig?.cardTheme}
              trend={currentReport.chartConfig?.trend}
              comparisonValue={currentReport.chartConfig?.comparisonValue}
              gaugeMin={currentReport.chartConfig?.gaugeMin}
              gaugeMax={currentReport.chartConfig?.gaugeMax}
              gaugeThresholds={currentReport.chartConfig?.gaugeThresholds}
            />
            {queryParams && Object.keys(queryParams).length > 0 && (
              <div className="mt-4 text-sm text-gray-600">
                查询参数: {JSON.stringify(queryParams)}
              </div>
            )}
          </div>
        </div>
      );
    }

    // Fallback for other report types or no data
    return (
      <div className="p-6">
        <h3 className="text-xl font-bold text-gray-900 mb-4">{currentReport.name}</h3>
        <p className="text-gray-600 mb-6">{currentReport.description}</p>
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <p className="text-sm text-gray-800">
            {displayedReportData === undefined ? '正在加载数据...' : '此报表没有数据或无法显示。'}
          </p>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">
            {currentReport ? currentReport.name : '报表'}
          </h2>
          <p className="text-gray-600 mt-1">
            {currentReport ? currentReport.description : '生产数据统计分析与报表管理'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* 只有当前报表有 SQL 查询时才显示刷新按钮 */}
          {currentReport && currentReport.sqlQuery && (
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              {isRefreshing ? '刷新中...' : '刷新数据'}
            </button>
          )}
          {currentReport && currentReport.type !== 'mes-chat' && (
            <button className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2">
              <Download className="w-4 h-4" />
              导出报表
            </button>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        {renderReportContent()}
      </div>
    </div>
  );
};