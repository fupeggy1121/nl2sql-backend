/**
 * Intent Recognizer Service
 * Analyzes user input to determine query intent and whether clarifications are needed
 */

/**
 * Detects if the input is a direct table query (should NOT ask for clarifications)
 * Examples:
 * - "返回 wafers 表的前300条数据"
 * - "查询 wafers 表"
 * - "SELECT * FROM wafers LIMIT 300"
 */
function isDirectTableQuery(input) {
  // Keywords that indicate direct table queries
  const directQueryPatterns = [
    /返回.*表.*前?\d+.*数据/i, // "返回 X 表的前300条数据"
    /查询.*表/i, // "查询 X 表"
    /显示.*表/i, // "显示 X 表"
    /获取.*表/i, // "获取 X 表"
    /列出.*表/i, // "列出 X 表"
    /select\s+\*/i, // "SELECT * FROM..."
    /from\s+\w+/i, // "FROM table_name"
    /limit\s+\d+/i, // "LIMIT 300"
    /table\s*：/i, // Table indicator
    /表格/i, // "表格"
  ];

  // Check if input matches direct query patterns
  return directQueryPatterns.some(pattern => pattern.test(input));
}

/**
 * Extracts table name and limit from query
 */
function extractTableInfo(input) {
  const result = {};

  // Extract table name
  const tableMatch = input.match(/(?:查询|返回|显示|获取)?\s*(\w+)\s*表/);
  if (tableMatch) {
    result.table = tableMatch[1];
  }

  // Extract LIMIT value
  const limitMatch = input.match(/(?:前\s*)?(\d+)\s*(?:条|条数|行|rows)?/);
  if (limitMatch) {
    result.limit = parseInt(limitMatch[1], 10);
  }

  return result;
}

/**
 * Main intent recognition function
 */
function recognizeIntent(input) {
  // If it's a direct table query, no clarifications needed
  if (isDirectTableQuery(input)) {
    const tableInfo = extractTableInfo(input);
    return {
      type: 'direct_query',
      clarifications: [], // No clarifications for direct queries
      entities: {
        table: tableInfo.table,
        filters: tableInfo.limit ? { limit: tableInfo.limit } : {},
      },
      confidence: 0.95,
    };
  }

  // For other queries, determine if clarifications are needed
  const isAnalysisQuery = /(?:OEE|良率|效率|分析|对比|趋势|统计|排名|平均|最高|最低)/i.test(
    input
  );

  if (isAnalysisQuery) {
    // Extract metrics and other entities
    const metricsMatch = /(?:OEE|良率|效率|停机|产量)/gi.exec(input);
    const metric = metricsMatch ? metricsMatch[0] : undefined;

    const timeRangeMatch =
      /(?:最近|过去)?\s*(?:(\d+)\s*(?:天|周|月|小时|小时)|昨天|今天|本周|本月)/i.exec(input);
    const timeRange = timeRangeMatch ? timeRangeMatch[0] : undefined;

    // If metric is not specified, ask for clarification
    if (!metric) {
      return {
        type: 'analysis',
        clarifications: [
          '您想了解哪个具体指标？',
          '• OEE (Overall Equipment Effectiveness)',
          '• 良率 (Yield Rate)',
          '• 效率 (Efficiency)',
          '• 停机时间 (Downtime)',
        ],
        entities: {
          timeRange,
        },
        confidence: 0.6,
      };
    }

    return {
      type: 'analysis',
      clarifications: [], // Metric is specified, no clarifications needed
      entities: {
        metric,
        timeRange,
      },
      confidence: 0.85,
    };
  }

  // For other query types
  return {
    type: 'other',
    clarifications: [],
    entities: {},
    confidence: 0.5,
  };
}

/**
 * Export the recognizer object
 */
export const intentRecognizer = {
  recognizeIntent,
};
