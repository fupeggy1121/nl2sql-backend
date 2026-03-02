import { useEffect, useState } from 'react';
import { BarChart3, TrendingUp, MessageSquare, AlertCircle } from 'lucide-react';
import { feedbackService } from '../services/feedbackService';

interface Stats {
  totalFeedback: number;
  helpfulRate: number;
  averageRating: number;
  topIssues: { issue: string; count: number }[];
}

interface IntentStats {
  totalIntents: number;
  correctCount: number;
  accuracy: number;
  byIntent: Record<string, { total: number; correct: number; accuracy: number }>;
}

interface FeedbackStatsProps {
  isOpen: boolean;
  onClose: () => void;
}

export function FeedbackStats({ isOpen, onClose }: FeedbackStatsProps) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [intentStats, setIntentStats] = useState<IntentStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isOpen) {
      loadStats();
    }
  }, [isOpen]);

  const loadStats = async () => {
    setLoading(true);
    const [feedbackStats, intentAcc] = await Promise.all([
      feedbackService.getFeedbackStats(),
      feedbackService.getIntentAccuracy()
    ]);

    setStats(feedbackStats);
    setIntentStats(intentAcc);
    setLoading(false);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
            <BarChart3 className="w-6 h-6 text-blue-600" />
            反馈统计分析
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors text-2xl"
          >
            ×
          </button>
        </div>

        <div className="p-6">
          {loading ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
              <p className="mt-4 text-gray-600">加载统计数据中...</p>
            </div>
          ) : (
            <div className="space-y-8">
              {/* 反馈概览 */}
              {stats && (
                <div>
                  <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                    <MessageSquare className="w-5 h-5 text-blue-600" />
                    反馈概览
                  </h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4 border border-blue-200">
                      <p className="text-sm text-blue-600 font-semibold">总反馈数</p>
                      <p className="text-3xl font-bold text-blue-900 mt-2">
                        {stats.totalFeedback}
                      </p>
                    </div>

                    <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-4 border border-green-200">
                      <p className="text-sm text-green-600 font-semibold">有帮助比例</p>
                      <p className="text-3xl font-bold text-green-900 mt-2">
                        {stats.helpfulRate.toFixed(1)}%
                      </p>
                    </div>

                    <div className="bg-gradient-to-br from-yellow-50 to-yellow-100 rounded-lg p-4 border border-yellow-200">
                      <p className="text-sm text-yellow-600 font-semibold">平均评分</p>
                      <p className="text-3xl font-bold text-yellow-900 mt-2">
                        {stats.averageRating.toFixed(2)}
                        <span className="text-lg">★</span>
                      </p>
                    </div>

                    <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4 border border-purple-200">
                      <p className="text-sm text-purple-600 font-semibold">需改进</p>
                      <p className="text-3xl font-bold text-purple-900 mt-2">
                        {stats.topIssues.length}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* 主要问题 */}
              {stats && stats.topIssues.length > 0 && (
                <div>
                  <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                    <AlertCircle className="w-5 h-5 text-red-600" />
                    用户反馈的主要问题
                  </h3>
                  <div className="space-y-3">
                    {stats.topIssues.map((issue, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-4 bg-red-50 border border-red-200 rounded-lg"
                      >
                        <div className="flex-1">
                          <p className="text-gray-700 font-medium">{issue.issue}</p>
                        </div>
                        <div className="ml-4">
                          <span className="px-3 py-1 bg-red-200 text-red-700 rounded-full text-sm font-semibold">
                            {issue.count} 次
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 意图识别准确率 */}
              {intentStats && (
                <div>
                  <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-indigo-600" />
                    意图识别准确率
                  </h3>

                  <div className="bg-gradient-to-r from-indigo-50 to-indigo-100 rounded-lg p-6 border border-indigo-200 mb-4">
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <p className="text-sm text-indigo-600 font-semibold">总样本</p>
                        <p className="text-3xl font-bold text-indigo-900 mt-2">
                          {intentStats.totalIntents}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-indigo-600 font-semibold">正确识别</p>
                        <p className="text-3xl font-bold text-indigo-900 mt-2">
                          {intentStats.correctCount}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-indigo-600 font-semibold">准确率</p>
                        <p className="text-3xl font-bold text-indigo-900 mt-2">
                          {intentStats.accuracy.toFixed(1)}%
                        </p>
                      </div>
                    </div>

                    <div className="mt-4 h-2 bg-indigo-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-green-400 to-indigo-600 transition-all"
                        style={{ width: `${intentStats.accuracy}%` }}
                      />
                    </div>
                  </div>

                  {Object.keys(intentStats.byIntent).length > 0 && (
                    <div className="space-y-3">
                      <p className="text-sm font-semibold text-gray-700">按意图类型分布：</p>
                      {Object.entries(intentStats.byIntent)
                        .sort((a, b) => b[1].total - a[1].total)
                        .map(([intent, stats]) => (
                          <div key={intent} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                            <div className="flex items-center justify-between mb-2">
                              <span className="font-medium text-gray-700 truncate">{intent}</span>
                              <span className="text-xs font-semibold text-gray-500">
                                {stats.total} 样本
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-gradient-to-r from-green-400 to-blue-600"
                                  style={{ width: `${stats.accuracy}%` }}
                                />
                              </div>
                              <span className="text-sm font-bold text-gray-700 min-w-fit">
                                {stats.accuracy.toFixed(1)}%
                              </span>
                            </div>
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              )}

              {/* 建议 */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <h4 className="font-semibold text-blue-900 mb-2">基于反馈的改进建议</h4>
                <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
                  {stats && stats.helpfulRate < 70 && (
                    <li>考虑改进查询理解和意图识别算法</li>
                  )}
                  {intentStats && intentStats.accuracy < 85 && (
                    <li>需要优化意图识别模型，特别关注低准确率的意图类型</li>
                  )}
                  {stats && stats.topIssues.length > 0 && (
                    <li>重点解决用户反馈的常见问题</li>
                  )}
                  {stats && stats.averageRating < 3.5 && (
                    <li>用户满意度需提升，建议深入分析反馈内容</li>
                  )}
                </ul>
              </div>
            </div>
          )}
        </div>

        <div className="border-t border-gray-200 px-6 py-4 flex justify-end">
          <button
            onClick={onClose}
            className="px-6 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors font-medium"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}
