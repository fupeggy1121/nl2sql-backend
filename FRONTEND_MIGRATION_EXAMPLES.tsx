/**
 * 前端迁移示例
 * 从旧的 intentRecognizer.ts + queryService.ts 迁移到新的 nl2sqlApi_v2.js
 */

// ============================================
// ❌ 旧代码 (已删除的文件)
// ============================================

// intentRecognizer.ts 中的使用
/* 旧方式
import { recognizeIntent } from '@/services/intentRecognizer';

async function oldIntentRecognition(query: string) {
  const intent = await recognizeIntent(query);
  return {
    type: intent.query_type,
    metric: intent.metric,
    equipment: intent.equipment,
    timeRange: intent.time_range
  };
}
*/

// queryService.ts 中的使用
/* 旧方式
import { queryService } from '@/services/queryService';

async function oldQueryExecution(intent: Intent) {
  const result = await queryService.executeQuery(intent);
  return {
    data: result.data,
    sql: result.sql,
    timestamp: result.timestamp
  };
}
*/

// ============================================
// ✅ 新代码 (使用 nl2sqlApi_v2.js)
// ============================================

import nl2sqlApi from '@/services/nl2sqlApi_v2';

/**
 * 新方式1: 基础查询流程
 * 适用于简单的、明确的查询
 */
async function newBasicQuery(userQuery: string) {
  // 第1步: 生成SQL（不执行）
  const explainResponse = await nl2sqlApi.explainQuery(userQuery);
  
  if (!explainResponse.success) {
    console.error('SQL生成失败:', explainResponse.error);
    return null;
  }

  const plan = explainResponse.query_plan;

  // 检查是否需要澄清
  if (plan.requires_clarification) {
    console.log('需要澄清:', plan.clarification_message);
    console.log('问题:', plan.clarification_questions);
    // 应该显示UI给用户，让其回答问题
    return { status: 'needs_clarification', plan };
  }

  // 第2步: 显示SQL给用户审核
  console.log('生成的SQL:', plan.generated_sql);
  console.log('说明:', plan.explanation);
  // UI应该让用户审核和编辑SQL

  // 第3步: 执行SQL（假设用户已批准）
  const executeResponse = await nl2sqlApi.executeApprovedQuery(
    plan.generated_sql,
    plan.query_intent
  );

  if (!executeResponse.success) {
    console.error('执行失败:', executeResponse.error);
    return null;
  }

  return {
    status: 'success',
    result: executeResponse.query_result
  };
}

/**
 * 新方式2: 完整工作流（处理澄清）
 * 适用于需要澄清或提供用户反馈的查询
 */
async function newCompleteWorkflow(userQuery: string) {
  // 第1步: 处理自然语言查询
  const response = await nl2sqlApi.processNaturalLanguageQuery(
    userQuery,
    { executeDirectly: false }  // 先审核再执行
  );

  if (!response.success) {
    return { error: response.error };
  }

  const plan = response.query_plan;

  // 第2步: 检查是否需要澄清
  if (plan.requires_clarification) {
    return {
      status: 'clarification_needed',
      message: plan.clarification_message,
      questions: plan.clarification_questions,
      plan: plan
    };
  }

  // 第3步: 返回SQL供用户审核
  return {
    status: 'ready_for_approval',
    sql: plan.generated_sql,
    explanation: plan.explanation,
    variants: plan.suggested_sql_variants,
    intent: plan.query_intent
  };
}

/**
 * 新方式3: React 组件中的使用
 * 展示完整的状态管理和UI流程
 */
import React, { useState } from 'react';

export const MigratedQueryComponent = () => {
  // 状态: input | clarify | explain | execute | results
  const [step, setStep] = useState('input');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // 查询相关
  const [userQuery, setUserQuery] = useState('');
  const [queryPlan, setQueryPlan] = useState(null);
  const [editedSQL, setEditedSQL] = useState('');

  // 结果相关
  const [queryResult, setQueryResult] = useState(null);
  const [clarificationAnswers, setClarificationAnswers] = useState({});

  // ===== 步骤1: 输入查询 =====
  const handleInputQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userQuery.trim()) {
      setError('请输入查询内容');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // 调用后端API
      const response = await nl2sqlApi.explainQuery(userQuery);

      if (!response.success) {
        setError(response.error || '查询失败');
        return;
      }

      const plan = response.query_plan;

      if (plan.requires_clarification) {
        // 需要澄清
        setQueryPlan(plan);
        setStep('clarify');
      } else {
        // 可以直接显示SQL
        setQueryPlan(plan);
        setEditedSQL(plan.generated_sql);
        setStep('explain');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '处理查询时出错');
    } finally {
      setLoading(false);
    }
  };

  // ===== 步骤2: 澄清查询 =====
  const handleClarification = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // 获取用户的澄清答案
      const clarifications = Object.entries(clarificationAnswers)
        .map(([question, answer]) => `${question}: ${answer}`)
        .join('; ');

      // 用澄清信息重新生成SQL
      const clarifiedQuery = `${userQuery}\n(澄清: ${clarifications})`;
      
      const response = await nl2sqlApi.explainQuery(clarifiedQuery);

      if (!response.success) {
        setError(response.error || '重新生成失败');
        return;
      }

      const plan = response.query_plan;
      
      if (!plan.requires_clarification) {
        setQueryPlan(plan);
        setEditedSQL(plan.generated_sql);
        setStep('explain');
      } else {
        setError('仍需进一步澄清');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '处理澄清时出错');
    } finally {
      setLoading(false);
    }
  };

  // ===== 步骤3: 审核SQL =====
  const handleApproveSQL = async () => {
    if (!editedSQL.trim()) {
      setError('SQL不能为空');
      return;
    }

    // 可选: 验证SQL
    const validateRes = await nl2sqlApi.validateSQL(editedSQL);
    if (!validateRes.success) {
      setError('SQL语法错误: ' + validateRes.errors?.join(', '));
      return;
    }

    setStep('execute');
    setLoading(true);
    setError(null);

    try {
      const response = await nl2sqlApi.executeApprovedQuery(
        editedSQL,
        queryPlan?.query_intent
      );

      if (!response.success) {
        setError(response.error || '执行失败');
        setStep('explain');
        return;
      }

      setQueryResult(response.query_result);
      setStep('results');
    } catch (err) {
      setError(err instanceof Error ? err.message : '执行时出错');
      setStep('explain');
    } finally {
      setLoading(false);
    }
  };

  // ===== 步骤4: 显示结果 =====
  const handleExportResults = () => {
    if (!queryResult) return;

    const csv = queryResult.data
      .map((row: any) => Object.values(row).join(','))
      .join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'query-results.csv';
    a.click();
  };

  // ===== 重置 =====
  const handleReset = () => {
    setStep('input');
    setUserQuery('');
    setQueryPlan(null);
    setEditedSQL('');
    setQueryResult(null);
    setError(null);
  };

  // ===== 获取推荐 =====
  const handleLoadRecommendations = async () => {
    try {
      const response = await nl2sqlApi.getQueryRecommendations();
      if (response.success) {
        console.log('推荐查询:', response.recommendations);
        // 可以显示这些推荐给用户
      }
    } catch (err) {
      console.error('获取推荐失败:', err);
    }
  };

  // ===== 获取执行历史 =====
  const handleLoadHistory = async () => {
    try {
      const response = await nl2sqlApi.getExecutionHistory();
      if (response.success) {
        console.log('执行历史:', response.history);
        // 可以显示历史查询给用户快速复用
      }
    } catch (err) {
      console.error('获取历史失败:', err);
    }
  };

  return (
    <div className="query-container">
      <h1>MES 查询工具</h1>

      {/* 步骤1: 输入 */}
      {step === 'input' && (
        <form onSubmit={handleInputQuery}>
          <textarea
            value={userQuery}
            onChange={(e) => setUserQuery(e.target.value)}
            placeholder="输入自然语言查询，例如：获取今天的OEE数据"
            rows={4}
          />
          <button type="submit" disabled={loading}>
            {loading ? '处理中...' : '生成SQL'}
          </button>
          <button type="button" onClick={handleLoadRecommendations}>
            查看推荐
          </button>
          <button type="button" onClick={handleLoadHistory}>
            查看历史
          </button>
          {error && <p className="error">{error}</p>}
        </form>
      )}

      {/* 步骤2: 澄清 */}
      {step === 'clarify' && queryPlan?.clarification_questions && (
        <form onSubmit={handleClarification}>
          <h2>需要澄清</h2>
          <p>{queryPlan.clarification_message}</p>
          
          {queryPlan.clarification_questions.map((question, i) => (
            <div key={i} className="clarification-item">
              <label>{question}</label>
              <input
                type="text"
                onChange={(e) =>
                  setClarificationAnswers({
                    ...clarificationAnswers,
                    [question]: e.target.value
                  })
                }
              />
            </div>
          ))}

          <button type="submit" disabled={loading}>
            {loading ? '处理中...' : '继续'}
          </button>
          <button type="button" onClick={handleReset}>
            返回
          </button>
          {error && <p className="error">{error}</p>}
        </form>
      )}

      {/* 步骤3: 审核SQL */}
      {step === 'explain' && queryPlan && (
        <div>
          <h2>审核生成的SQL</h2>

          {queryPlan.explanation && (
            <div className="explanation">
              <h3>说明</h3>
              <p>{queryPlan.explanation}</p>
            </div>
          )}

          <div className="sql-editor">
            <h3>SQL查询</h3>
            <textarea
              value={editedSQL}
              onChange={(e) => setEditedSQL(e.target.value)}
              rows={6}
            />
          </div>

          {queryPlan.suggested_sql_variants && queryPlan.suggested_sql_variants.length > 0 && (
            <div className="variants">
              <h3>其他建议</h3>
              {queryPlan.suggested_sql_variants.map((variant, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setEditedSQL(variant)}
                  className="variant-button"
                >
                  变体 {i + 1}
                </button>
              ))}
            </div>
          )}

          <button onClick={handleApproveSQL} disabled={loading}>
            {loading ? '执行中...' : '执行查询'}
          </button>
          <button onClick={handleReset}>
            返回
          </button>
          {error && <p className="error">{error}</p>}
        </div>
      )}

      {/* 步骤4: 执行中 */}
      {step === 'execute' && (
        <div>
          <p>正在执行查询...</p>
          <div className="loading-spinner" />
        </div>
      )}

      {/* 步骤5: 结果 */}
      {step === 'results' && queryResult && (
        <div>
          <h2>查询结果</h2>

          {queryResult.summary && (
            <div className="summary">
              <h3>摘要</h3>
              <p>{queryResult.summary}</p>
            </div>
          )}

          <div className="results-table">
            <h3>数据 ({queryResult.rows_count} 行)</h3>
            <table>
              <thead>
                <tr>
                  {Object.keys(queryResult.data[0] || {}).map((key) => (
                    <th key={key}>{key}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {queryResult.data.slice(0, 20).map((row, i) => (
                  <tr key={i}>
                    {Object.values(row).map((val, j) => (
                      <td key={j}>{String(val)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {queryResult.data.length > 20 && (
              <p>... 还有 {queryResult.data.length - 20} 行</p>
            )}
          </div>

          {queryResult.visualization_type && (
            <div className="visualization">
              <h3>推荐图表: {queryResult.visualization_type}</h3>
              {/* 这里可以集成 recharts 或其他图表库 */}
            </div>
          )}

          <button onClick={handleExportResults}>
            导出为CSV
          </button>
          <button onClick={handleReset}>
            新建查询
          </button>
        </div>
      )}
    </div>
  );
};

// ============================================
// 其他常见迁移场景
// ============================================

/**
 * 场景1: 列表查询 (获取所有记录)
 * 旧: queryService.listRecords(entity)
 * 新: 使用 explainQuery 询问后端
 */
export async function migrateListQuery(entity: string) {
  const query = `获取所有${entity}的记录`;
  return await nl2sqlApi.explainQuery(query);
}

/**
 * 场景2: 搜索和过滤
 * 旧: queryService.search(filters)
 * 新: 使用 processNaturalLanguageQuery
 */
export async function migrateSearchQuery(filters: any) {
  const query = `${filters.keyword}中的${filters.entity}`;
  return await nl2sqlApi.processNaturalLanguageQuery(query);
}

/**
 * 场景3: 聚合查询 (求和、平均等)
 * 旧: intentRecognizer识别意图 + queryService执行
 * 新: 直接调用 processNaturalLanguageQuery
 */
export async function migrateAggregateQuery(metric: string, dimensions: string[]) {
  const query = `${dimensions.join('和')}按${metric}统计`;
  const result = await nl2sqlApi.processNaturalLanguageQuery(query);
  return result;
}

/**
 * 场景4: 时间序列查询
 * 旧: 需要特殊处理时间维度
 * 新: 后端会自动识别时间相关的查询
 */
export async function migrateTimeSeriesQuery(metric: string, timeRange: string) {
  const query = `${timeRange}内每天的${metric}趋势`;
  return await nl2sqlApi.explainQuery(query);
}

export default {
  newBasicQuery,
  newCompleteWorkflow,
  MigratedQueryComponent,
  migrateListQuery,
  migrateSearchQuery,
  migrateAggregateQuery,
  migrateTimeSeriesQuery
};
