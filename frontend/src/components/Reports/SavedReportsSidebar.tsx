// src/components/Reports/SavedReportsSidebar.tsx
import React from 'react';
import { SavedReport } from '../../data/mockSavedReports'; // 导入 SavedReport 接口
import { useData } from '../../hooks/useData'; // 导入 useData hook
import { Trash2 } from 'lucide-react'; // 导入删除图标

interface SavedReportsSidebarProps {
  activeReportId: string;
  onSelectReport: (reportId: string) => void;
}

export const SavedReportsSidebar: React.FC<SavedReportsSidebarProps> = ({
  activeReportId,
  onSelectReport,
}) => {
  const { savedReports, deleteSavedReport } = useData(); // 从 useData 获取保存的报表和删除函数

  const handleDeleteReport = async (reportId: string, reportName: string) => {
    if (window.confirm(`确定要删除报表 "${reportName}" 吗？`)) {
      try {
        await deleteSavedReport(reportId);
        alert('报表删除成功！');
        // 如果删除的是当前激活的报表，则默认选中 MES 数据分析
        if (activeReportId === reportId) {
          onSelectReport('mes-data-analysis');
        }
      } catch (error) {
        alert('删除报表失败！');
      }
    }
  };

  return (
    <div className="p-4 space-y-1">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">保存的报表与视图</h3>
      {savedReports.length === 0 ? (
        <div className="text-center py-4 text-gray-500 text-sm">
          暂无保存的报表。
          <br />
          请在MES数据分析页面生成报表后保存。
        </div>
      ) : (
        savedReports.map((report: SavedReport) => {
          const IconComponent = report.icon; // 直接使用从 SavedReport 导入的图标组件
          const isActive = activeReportId === report.id;

          return (
            <div
              key={report.id}
              className={`
                w-full flex items-center justify-between px-3 py-2 rounded-md text-sm font-medium
                transition-colors duration-200
                ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 border-r-2 border-blue-700'
                    : 'text-gray-700 hover:bg-gray-100 hover:text-blue-600'
                }
              `}
            >
              <button
                onClick={() => onSelectReport(report.id)}
                className="flex-1 flex items-center text-left"
              >
                {IconComponent && <IconComponent className={`w-4 h-4 mr-3 ${isActive ? 'text-blue-700' : 'text-gray-500'}`} />}
                <span className="flex-1">{report.name}</span>
              </button>
              <button
                onClick={() => handleDeleteReport(report.id, report.name)}
                className="text-red-500 hover:text-red-700 p-1 rounded-md"
                title="删除报表"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          );
        })
      )}
    </div>
  );
};
