import { BarChart3, Table as TableIcon, TrendingUp } from 'lucide-react';
import { EChartsVisualization } from './EChartsVisualization';

interface DataVisualizationProps {
  data: any[];
  type: 'table' | 'bar' | 'line' | 'pie' | 'scatter';
  title?: string;
  xAxisField?: string;
  yAxisField?: string;
  colorField?: string;
}

export function DataVisualization({
  data,
  type,
  title,
  xAxisField,
  yAxisField,
  colorField
}: DataVisualizationProps) {
  if (!data || data.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>暂无数据</p>
      </div>
    );
  }

  if (type === 'table') {
    return <DataTable data={data} />;
  }

  if (['bar', 'line', 'pie', 'scatter'].includes(type)) {
    return (
      <EChartsVisualization
        data={data}
        type={type as 'bar' | 'line' | 'pie' | 'scatter'}
        title={title}
        xAxisField={xAxisField}
        yAxisField={yAxisField}
        colorField={colorField}
      />
    );
  }

  return <DataTable data={data} />;
}

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
      defect_count: '不良数'
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
      return value.toFixed(2);
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
