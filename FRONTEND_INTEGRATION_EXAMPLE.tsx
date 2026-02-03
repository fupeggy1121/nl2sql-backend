/**
 * 前端集成示例
 * 展示如何使用新的后端统一查询服务
 */

import React, { useState } from 'react';
import nl2sqlApi from '../services/nl2sqlApi_v2';

/**
 * 统一查询界面组件
 * 演示完整的查询流程：输入 -> 生成SQL -> 审核 -> 执行 -> 显示结果
 */
export const UnifiedQueryUI = () => {
  const [userQuery, setUserQuery] = useState('');
  const [step, setStep] = useState('input'); // input | explain | execute | results
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // 查询计划
  const [queryPlan, setQueryPlan] = useState(null);
  
  // 查询结果
  const [queryResult, setQueryResult] = useState(null);
  
  // SQL编辑状态
  const [editedSQL, setEditedSQL] = useState('');
  const [selectedVariant, setSelectedVariant] = useState(0);

  /**
   * 第1步: 用户输入自然语言查询
   */
  const handleInputQuery = async (e) => {
    e.preventDefault();
    if (!userQuery.trim()) {
      setError('请输入查询内容');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // 调用后端API进行意图识别和SQL生成
      const response = await nl2sqlApi.explainQuery(userQuery);

      if (!response.success) {
        setError(response.error || '查询失败');
        setLoading(false);
        return;
      }

      const plan = response.query_plan;

      // 检查是否需要澄清
      if (plan.requires_clarification) {
        setQueryPlan(plan);
        setStep('clarify');
      } else if (plan.generated_sql) {
        // 进入SQL审核步骤
        setQueryPlan(plan);
        setEditedSQL(plan.generated_sql);
        setStep('explain');
      } else {
        setError('无法生成SQL');
      }
    } catch (err) {
      setError(err.message || '处理查询时出现错误');
    } finally {
      setLoading(false);
    }
  };

  /**
   * 第2步: 显示和审核SQL
   */
  const handleApproveSQL = async () => {
    if (!editedSQL.trim()) {
      setError('SQL不能为空');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // 执行SQL查询
      const response = await nl2sqlApi.executeApprovedQuery(
        editedSQL,
        queryPlan.query_intent
      );

      if (!response.success) {
        setError(response.error || '执行失败');
        setLoading(false);
        return;
      }

      setQueryResult(response.query_result);
      setStep('results');
    } catch (err) {
      setError(err.message || '执行查询时出现错误');
    } finally {
      setLoading(false);
    }
  };

  /**
   * 回到编辑SQL
   */
  const handleEditSQL = () => {
    setStep('explain');
    setError(null);
  };

  /**
   * 显示澄清问题界面
   */
  if (step === 'clarify' && queryPlan?.requires_clarification) {
    return (
      <div className="unified-query-panel">
        <h3>我需要了解更多信息</h3>
        <p>{queryPlan.clarification_message}</p>
        
        {queryPlan.clarification_questions && (
          <div className="clarification-questions">
            {queryPlan.clarification_questions.map((q, idx) => (
              <div key={idx} className="question">
                <p>❓ {q}</p>
                <input
                  type="text"
                  placeholder="请输入您的答案"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      // 组合新的查询
                      const newQuery = `${userQuery}。${e.target.value}`;
                      setUserQuery(newQuery);
                      handleInputQuery({ preventDefault: () => {} });
                    }
                  }}
                />
              </div>
            ))}
          </div>
        )}
        
        <button onClick={() => setStep('input')}>返回输入</button>
      </div>
    );
  }

  /**
   * 显示输入界面
   */
  if (step === 'input') {
    return (
      <div className="unified-query-panel">
        <h3>自然语言查询</h3>
        <p>描述您想要的数据，系统会自动生成SQL查询</p>
        
        <form onSubmit={handleInputQuery}>
          <textarea
            value={userQuery}
            onChange={(e) => setUserQuery(e.target.value)}
            placeholder="例如：查询今天各设备的OEE数据按设备对比"
            rows={3}
            disabled={loading}
          />
          
          <button type="submit" disabled={loading}>
            {loading ? '处理中...' : '生成SQL'}
          </button>
        </form>
        
        {error && <div className="error-message">{error}</div>}
        
        {/* 推荐查询 */}
        <div className="recommendations">
          <h4>推荐查询</h4>
          <button
            onClick={() => {
              setUserQuery('查询今天各设备的OEE数据');
              handleInputQuery({ preventDefault: () => {} });
            }}
          >
            查看今天的OEE
          </button>
          <button
            onClick={() => {
              setUserQuery('对比本周不同设备的效率差异');
              handleInputQuery({ preventDefault: () => {} });
            }}
          >
            对比设备效率
          </button>
          <button
            onClick={() => {
              setUserQuery('查询最近30天的产品良率趋势');
              handleInputQuery({ preventDefault: () => {} });
            }}
          >
            产品质量分析
          </button>
        </div>
      </div>
    );
  }

  /**
   * 显示SQL审核界面
   */
  if (step === 'explain' && queryPlan) {
    return (
      <div className="unified-query-panel">
        <h3>✅ SQL已生成，请审核</h3>
        
        {/* 查询意图摘要 */}
        <div className="query-intent-summary">
          <h4>查询意图</h4>
          <p>
            <strong>类型:</strong> {queryPlan.query_intent.query_type}
            <br />
            <strong>指标:</strong> {queryPlan.query_intent.metric || '未指定'}
            <br />
            <strong>时间范围:</strong> {queryPlan.query_intent.time_range || '未指定'}
            <br />
            <strong>置信度:</strong> {(queryPlan.query_intent.confidence * 100).toFixed(1)}%
          </p>
        </div>
        
        {/* SQL解释 */}
        {queryPlan.explanation && (
          <div className="sql-explanation">
            <h4>📝 SQL含义</h4>
            <p>{queryPlan.explanation}</p>
          </div>
        )}
        
        {/* SQL编辑器 */}
        <div className="sql-editor">
          <h4>📋 生成的SQL</h4>
          <textarea
            value={editedSQL}
            onChange={(e) => setEditedSQL(e.target.value)}
            rows={8}
            className="sql-textarea"
          />
          <small>您可以编辑SQL后执行</small>
        </div>
        
        {/* SQL变体 */}
        {queryPlan.suggested_sql_variants && queryPlan.suggested_sql_variants.length > 0 && (
          <div className="sql-variants">
            <h4>💡 建议的SQL变体</h4>
            {queryPlan.suggested_sql_variants.map((variant, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setEditedSQL(variant);
                  setSelectedVariant(idx);
                }}
                className={selectedVariant === idx + 1 ? 'selected' : ''}
              >
                方案 {idx + 1}
              </button>
            ))}
          </div>
        )}
        
        {/* 操作按钮 */}
        <div className="actions">
          <button
            onClick={handleApproveSQL}
            disabled={loading}
            className="primary-btn"
          >
            {loading ? '执行中...' : '✅ 执行查询'}
          </button>
          <button
            onClick={() => setStep('input')}
            disabled={loading}
            className="secondary-btn"
          >
            🔙 返回修改
          </button>
        </div>
        
        {error && <div className="error-message">{error}</div>}
      </div>
    );
  }

  /**
   * 显示查询结果
   */
  if (step === 'results' && queryResult) {
    return (
      <div className="unified-query-panel">
        <h3>📊 查询结果</h3>
        
        {/* 结果摘要 */}
        <div className="result-summary">
          <p>
            <strong>状态:</strong> {queryResult.success ? '✅ 成功' : '❌ 失败'}
            <br />
            <strong>返回行数:</strong> {queryResult.rows_count}
            <br />
            <strong>查询耗时:</strong> {queryResult.query_time_ms.toFixed(2)}ms
            <br />
            <strong>摘要:</strong> {queryResult.summary}
          </p>
        </div>
        
        {/* 数据表格或图表 */}
        <div className="result-visualization">
          <h4>数据({queryResult.visualization_type})</h4>
          {queryResult.visualization_type === 'table' && (
            <ResultTable data={queryResult.data} />
          )}
          {queryResult.visualization_type === 'bar' && (
            <BarChart data={queryResult.data} />
          )}
          {queryResult.visualization_type === 'line' && (
            <LineChart data={queryResult.data} />
          )}
        </div>
        
        {/* 生成的SQL显示 */}
        <div className="executed-sql">
          <h4>🔍 执行的SQL</h4>
          <pre>{queryResult.sql}</pre>
        </div>
        
        {/* 可用操作 */}
        {queryResult.actions && queryResult.actions.length > 0 && (
          <div className="available-actions">
            <h4>可用操作</h4>
            <div className="action-buttons">
              {queryResult.actions.includes('export') && (
                <button onClick={() => exportData(queryResult.data)}>
                  📥 导出
                </button>
              )}
              {queryResult.actions.includes('detail') && (
                <button onClick={() => alert('展示详细信息')}>
                  🔎 详情
                </button>
              )}
              {queryResult.actions.includes('drilldown') && (
                <button onClick={() => alert('钻取分析')}>
                  🔍 下钻
                </button>
              )}
              {queryResult.actions.includes('schedule') && (
                <button onClick={() => alert('定时任务')}>
                  ⏱️ 定时
                </button>
              )}
            </div>
          </div>
        )}
        
        {/* 返回按钮 */}
        <button
          onClick={() => {
            setStep('input');
            setUserQuery('');
            setQueryPlan(null);
            setQueryResult(null);
            setError(null);
          }}
          className="secondary-btn"
        >
          🔙 新建查询
        </button>
      </div>
    );
  }

  return null;
};

/**
 * 结果表格组件
 */
const ResultTable = ({ data }) => {
  if (!data || data.length === 0) return <p>暂无数据</p>;

  const columns = Object.keys(data[0]);

  return (
    <table className="result-table">
      <thead>
        <tr>
          {columns.map((col) => (
            <th key={col}>{col}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((row, idx) => (
          <tr key={idx}>
            {columns.map((col) => (
              <td key={col}>{row[col]}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
};

/**
 * 柱状图组件
 */
const BarChart = ({ data }) => {
  return <div className="chart placeholder">柱状图 (待实现)</div>;
};

/**
 * 折线图组件
 */
const LineChart = ({ data }) => {
  return <div className="chart placeholder">折线图 (待实现)</div>;
};

/**
 * 导出数据
 */
function exportData(data) {
  const csv = [
    Object.keys(data[0]).join(','),
    ...data.map((row) => Object.values(row).join(','))
  ].join('\n');

  const blob = new Blob([csv], { type: 'text/csv' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'query_result.csv';
  a.click();
}

export default UnifiedQueryUI;
