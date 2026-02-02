/**
 * Intent Recognizer Service - Hybrid Rule + LLM Approach
 * Analyzes user input to determine query intent and whether clarifications are needed
 * 
 * Strategy:
 * 1. Fast rule-based matching for low latency
 * 2. LLM confirmation when rules are uncertain
 * 3. Entity extraction from both methods
 */

export interface Intent {
  type: 'direct_query' | 'analysis' | 'report' | 'query_equipment' | 'compare_analysis' | 'other';
  clarifications: string[];
  entities: {
    table?: string;
    metric?: string;
    timeRange?: string;
    filters?: Record<string, any>;
    productLine?: string;
    equipment?: string;
    defectType?: string;
  };
  confidence: number;
  methodsUsed: ('rule' | 'llm')[];
}

// Intent configuration with keywords and entity types
const INTENT_CONFIG: Record<string, {
  keywords: string[];
  entities: string[];
}> = {
  direct_query: {
    keywords: ['返回', '查询', '显示', '获取', '列出', '表', 'select', 'from'],
    entities: ['table', 'limit', 'filters']
  },
  query_production: {
    keywords: ['产量', '生产', '产出', '完成', '输出'],
    entities: ['timeRange', 'productLine', 'productType']
  },
  query_quality: {
    keywords: ['良品率', '合格率', '质量', '不良', '缺陷', '良率'],
    entities: ['timeRange', 'productType', 'defectType']
  },
  query_equipment: {
    keywords: ['设备', '稼动率', 'OEE', '故障', '停机', '效率', '设备'],
    entities: ['timeRange', 'equipmentId', 'workshop']
  },
  generate_report: {
    keywords: ['报表', '生成', '导出', '汇总', '统计', '汇报'],
    entities: ['reportType', 'timeRange']
  },
  compare_analysis: {
    keywords: ['对比', '比较', '同比', '环比', '分析', '趋势'],
    entities: ['timeRange', 'metric']
  }
};

/**
 * Rule-based quick matching (low latency)
 * Returns confidence score and matched intent
 */
function ruleBasedMatch(input: string): {
  intent: string;
  confidence: number;
  entities: Record<string, any>;
} {
  const normalizedInput = input.toLowerCase();
  const scores: Record<string, number> = {};

  // Calculate matching score for each intent
  for (const [intentName, config] of Object.entries(INTENT_CONFIG)) {
    let score = 0;
    const keywords = config.keywords;
    
    // Count keyword matches
    keywords.forEach(keyword => {
      if (normalizedInput.includes(keyword.toLowerCase())) {
        score += 1;
      }
    });

    if (score > 0) {
      // Normalize score by keyword count
      scores[intentName] = score / keywords.length;
    }
  }

  // If no matches found
  if (Object.keys(scores).length === 0) {
    return {
      intent: 'other',
      confidence: 0.0,
      entities: {}
    };
  }

  // Get best matching intent
  const bestIntent = Object.keys(scores).reduce((a, b) =>
    scores[a] > scores[b] ? a : b
  );

  return {
    intent: bestIntent,
    confidence: scores[bestIntent],
    entities: extractEntities(input, bestIntent)
  };
}

/**
 * Extract entities from user input using regex patterns
 */
function extractEntities(input: string, intent: string): Record<string, any> {
  const entities: Record<string, any> = {};

  // Extract time range
  const timePatterns: Record<string, string> = {
    '今天|今日': 'today',
    '昨天|昨日': 'yesterday',
    '本周|这周': 'this_week',
    '上周|上星期': 'last_week',
    '本月|这个月': 'this_month',
    '上月|上个月': 'last_month',
  };

  for (const [pattern, value] of Object.entries(timePatterns)) {
    if (new RegExp(pattern).test(input)) {
      entities.timeRange = value;
      break;
    }
  }

  // Extract numeric time range (e.g., "最近7天", "过去30天")
  const numTimeMatch = input.match(/(?:最近|过去|最)?\s*(\d+)\s*(?:天|周|月)/);
  if (numTimeMatch) {
    entities.timeRange = `${numTimeMatch[1]} ${numTimeMatch[0].match(/天|周|月/)}`;
  }

  // Extract table name (for direct queries)
  const tableMatch = input.match(/(?:查询|返回|显示|获取)?\s*(\w+)\s*表/);
  if (tableMatch) {
    entities.table = tableMatch[1];
  }

  // Extract limit value
  const limitMatch = input.match(/(?:前\s*)?(\d+)\s*(?:条|条数|行|rows)?/);
  if (limitMatch) {
    entities.limit = parseInt(limitMatch[1], 10);
  }

  // Extract metric information
  const metricMapping: Record<string, string> = {
    '产量': 'output_qty',
    '良品率': 'yield_rate',
    '良率': 'yield_rate',
    'oee': 'oee',
    '稼动率': 'utilization_rate',
    '效率': 'efficiency',
    '停机': 'downtime'
  };

  for (const [keyword, metric] of Object.entries(metricMapping)) {
    if (input.includes(keyword)) {
      if (!entities.metrics) entities.metrics = [];
      entities.metrics.push(metric);
    }
  }

  // Extract product line
  const productLineMatch = input.match(/(?:产品线|产线)\s*[:：]?\s*(\w+)/);
  if (productLineMatch) {
    entities.productLine = productLineMatch[1];
  }

  // Extract equipment ID
  const equipmentMatch = input.match(/(?:设备|设备号|设备ID)\s*[:：]?\s*(\w+)/);
  if (equipmentMatch) {
    entities.equipment = equipmentMatch[1];
  }

  return entities;
}

/**
 * LLM-based intent matching for uncertain cases
 * Uses DeepSeek API for more accurate intent determination
 */
async function llmBasedMatch(input: string): Promise<{
  intent: string;
  confidence: number;
  entities: Record<string, any>;
  reasoning?: string;
}> {
  try {
    // Check if we have access to DeepSeek API
    const apiKey = process.env.REACT_APP_DEEPSEEK_API_KEY;
    if (!apiKey) {
      console.warn('DeepSeek API key not found, skipping LLM matching');
      return {
        intent: 'other',
        confidence: 0.0,
        entities: {}
      };
    }

    const intentList = Object.keys(INTENT_CONFIG).join(', ');
    const prompt = `分析用户在MES系统中的查询意图。

可能的意图类型: ${intentList}

用户输入: "${input}"

请返回 JSON 格式的分析结果（必须是有效的JSON）:
{
    "intent": "意图类型",
    "confidence": 0.95,
    "entities": {
        "timeRange": "时间范围",
        "metric": "指标",
        "table": "表名"
    },
    "reasoning": "判断理由"
}`;

    // Call DeepSeek API
    const response = await fetch('https://api.deepseek.com/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model: 'deepseek-chat',
        messages: [
          {
            role: 'system',
            content: '你是一个MES系统的意图识别助手，严格返回JSON格式的分析结果。'
          },
          {
            role: 'user',
            content: prompt
          }
        ],
        temperature: 0.1,
        response_format: { type: 'json_object' }
      })
    });

    if (!response.ok) {
      console.warn(`DeepSeek API error: ${response.status}`);
      return {
        intent: 'other',
        confidence: 0.0,
        entities: {}
      };
    }

    const data = await response.json();
    const content = data.choices?.[0]?.message?.content;
    
    if (!content) {
      return {
        intent: 'other',
        confidence: 0.0,
        entities: {}
      };
    }

    // Parse JSON response
    const result = JSON.parse(content);
    
    return {
      intent: result.intent || 'other',
      confidence: result.confidence || 0.0,
      entities: result.entities || {},
      reasoning: result.reasoning
    };
  } catch (error) {
    console.error('LLM matching error:', error);
    return {
      intent: 'other',
      confidence: 0.0,
      entities: {}
    };
  }
}

/**
 * Merge rule-based and LLM results
 * Prioritize LLM results when available, merge entities from both
 */
function mergeResults(
  ruleResult: { intent: string; confidence: number; entities: Record<string, any> },
  llmResult: { intent: string; confidence: number; entities: Record<string, any>; reasoning?: string }
): { intent: string; confidence: number; entities: Record<string, any>; reasoning?: string; methodsUsed: ('rule' | 'llm')[] } {
  const methodsUsed: ('rule' | 'llm')[] = ['rule'];
  
  let finalIntent = ruleResult.intent;
  let finalConfidence = ruleResult.confidence;
  
  // Use LLM result if it has higher confidence or was called
  if (llmResult.confidence > 0.5) {
    methodsUsed.push('llm');
    finalIntent = llmResult.intent;
    finalConfidence = Math.max(ruleResult.confidence, llmResult.confidence);
  }

  // Merge entities from both methods
  const mergedEntities = {
    ...ruleResult.entities,
    ...llmResult.entities
  };

  return {
    intent: finalIntent,
    confidence: finalConfidence,
    entities: mergedEntities,
    reasoning: llmResult.reasoning,
    methodsUsed
  };
}

/**
 * Determine clarifications needed based on intent and entities
 */
function determineClarifications(
  intent: string,
  entities: Record<string, any>,
  confidence: number
): string[] {
  const clarifications: string[] = [];

  // If confidence is too low, ask for clarification
  if (confidence < 0.5) {
    clarifications.push('您的意图不够清晰，请提供更多信息。');
    return clarifications;
  }

  // Intent-specific clarification logic
  switch (intent) {
    case 'query_production':
      if (!entities.timeRange) {
        clarifications.push('请指定您想查询的时间范围（如：今天、本周、上月）');
      }
      if (!entities.productLine && !entities.productType) {
        clarifications.push('请指定具体的产品线或产品类型');
      }
      break;

    case 'query_quality':
      if (!entities.timeRange) {
        clarifications.push('请指定您想查询的时间范围');
      }
      if (!entities.metrics || entities.metrics.length === 0) {
        clarifications.push('您想了解哪个质量指标？• 良品率 • 合格率 • 缺陷率');
      }
      break;

    case 'query_equipment':
      if (!entities.metrics || entities.metrics.length === 0) {
        clarifications.push('您想了解哪个设备指标？• OEE • 稼动率 • 故障时间');
      }
      if (!entities.timeRange) {
        clarifications.push('请指定查询时间范围');
      }
      break;

    case 'generate_report':
      if (!entities.reportType) {
        clarifications.push('请指定报表类型（如：日报、周报、月报、生产报表、质量报表）');
      }
      if (!entities.timeRange) {
        clarifications.push('请指定报表的时间范围');
      }
      break;

    case 'compare_analysis':
      if (!entities.metrics || entities.metrics.length === 0) {
        clarifications.push('请指定要对比的指标');
      }
      if (!entities.timeRange) {
        clarifications.push('请指定对比的时间范围（如：同比、环比）');
      }
      break;

    case 'direct_query':
      // Direct queries don't need clarifications
      break;

    default:
      if (confidence < 0.7) {
        clarifications.push('请提供更具体的查询条件');
      }
  }

  return clarifications;
}

/**
 * Main hybrid intent recognition function
 * Strategy: Rule-based first, LLM confirmation if uncertain
 */
export async function recognizeIntent(input: string): Promise<Intent> {
  // Step 1: Fast rule-based matching
  const ruleResult = ruleBasedMatch(input);

  // Step 2: If confidence is high enough, return rule result
  if (ruleResult.confidence > 0.8) {
    const clarifications = determineClarifications(
      ruleResult.intent,
      ruleResult.entities,
      ruleResult.confidence
    );

    return {
      type: (ruleResult.intent as any),
      clarifications,
      entities: ruleResult.entities,
      confidence: ruleResult.confidence,
      methodsUsed: ['rule']
    };
  }

  // Step 3: LLM confirmation for uncertain cases
  const llmResult = await llmBasedMatch(input);
  const mergedResult = mergeResults(ruleResult, llmResult);

  const clarifications = determineClarifications(
    mergedResult.intent,
    mergedResult.entities,
    mergedResult.confidence
  );

  return {
    type: (mergedResult.intent as any),
    clarifications,
    entities: mergedResult.entities,
    confidence: mergedResult.confidence,
    methodsUsed: mergedResult.methodsUsed
  };
}

/**
 * Synchronous version for use in components that don't support async
 * Falls back to rule-based matching only if LLM is not available
 */
export function recognizeIntentSync(input: string): Intent {
  const ruleResult = ruleBasedMatch(input);
  
  const clarifications = determineClarifications(
    ruleResult.intent,
    ruleResult.entities,
    ruleResult.confidence
  );

  return {
    type: (ruleResult.intent as any),
    clarifications,
    entities: ruleResult.entities,
    confidence: ruleResult.confidence,
    methodsUsed: ['rule']
  };
}

/**
 * Export the recognizer service
 */
export const intentRecognizer = {
  recognizeIntent,
  recognizeIntentSync,
  INTENT_CONFIG
};
