/**
 * Intent Recognizer Service - Test Cases
 * Demonstrates the hybrid rule + LLM approach
 */

import { recognizeIntent, recognizeIntentSync, Intent } from './intentRecognizer';

/**
 * Test cases for different intent types
 */
const testCases = [
  // Direct query cases - should have high confidence with rules only
  {
    input: '返回 wafers 表的前300条数据',
    expectedIntent: 'direct_query',
    expectedEntities: ['table', 'limit']
  },
  {
    input: '查询 users 表',
    expectedIntent: 'direct_query',
    expectedEntities: ['table']
  },
  {
    input: 'SELECT * FROM wafers LIMIT 100',
    expectedIntent: 'direct_query',
    expectedEntities: ['table', 'limit']
  },

  // Production query cases
  {
    input: '查询今天的产量',
    expectedIntent: 'query_production',
    expectedEntities: ['timeRange']
  },
  {
    input: '最近7天的生产数据',
    expectedIntent: 'query_production',
    expectedEntities: ['timeRange']
  },

  // Quality query cases
  {
    input: '本月的良品率是多少',
    expectedIntent: 'query_quality',
    expectedEntities: ['timeRange', 'metrics']
  },
  {
    input: '昨天的缺陷数据',
    expectedIntent: 'query_quality',
    expectedEntities: ['timeRange']
  },

  // Equipment query cases
  {
    input: '设备A的OEE',
    expectedIntent: 'query_equipment',
    expectedEntities: ['equipment', 'metrics']
  },
  {
    input: '今天的设备稼动率',
    expectedIntent: 'query_equipment',
    expectedEntities: ['timeRange', 'metrics']
  },

  // Report generation cases
  {
    input: '生成本月的生产报表',
    expectedIntent: 'generate_report',
    expectedEntities: ['timeRange']
  },
  {
    input: '导出本周的质量汇总',
    expectedIntent: 'generate_report',
    expectedEntities: ['timeRange']
  },

  // Compare and analysis cases
  {
    input: '比较本月和上月的产量',
    expectedIntent: 'compare_analysis',
    expectedEntities: ['metrics']
  },
  {
    input: '分析最近30天的良率趋势',
    expectedIntent: 'compare_analysis',
    expectedEntities: ['timeRange', 'metrics']
  }
];

/**
 * Run synchronous tests
 */
export function runSyncTests(): void {
  console.log('=== Intent Recognizer Sync Tests ===\n');

  let passed = 0;
  let failed = 0;

  for (const testCase of testCases) {
    const result = recognizeIntentSync(testCase.input);
    
    const intentMatch = result.type === testCase.expectedIntent;
    const entitiesMatch = testCase.expectedEntities.every(entity =>
      result.entities[entity as keyof typeof result.entities] !== undefined ||
      (entity === 'metrics' && result.entities.metrics?.length)
    );

    const success = intentMatch && entitiesMatch;

    console.log(`Test: "${testCase.input}"`);
    console.log(`Expected Intent: ${testCase.expectedIntent}, Got: ${result.type}`);
    console.log(`Expected Entities: ${testCase.expectedEntities.join(', ')}`);
    console.log(`Got Entities: ${Object.keys(result.entities).join(', ')}`);
    console.log(`Confidence: ${result.confidence.toFixed(2)}`);
    console.log(`Methods Used: ${result.methodsUsed.join(', ')}`);
    console.log(`Status: ${success ? '✅ PASS' : '❌ FAIL'}`);
    
    if (result.clarifications.length > 0) {
      console.log(`Clarifications needed: ${result.clarifications.join('; ')}`);
    }
    
    console.log('---\n');

    if (success) passed++;
    else failed++;
  }

  console.log(`\nResults: ${passed} passed, ${failed} failed out of ${testCases.length} tests`);
}

/**
 * Run async tests with LLM
 */
export async function runAsyncTests(): Promise<void> {
  console.log('=== Intent Recognizer Async Tests (with LLM) ===\n');

  let passed = 0;
  let failed = 0;

  for (const testCase of testCases) {
    const result = await recognizeIntent(testCase.input);
    
    const intentMatch = result.type === testCase.expectedIntent;
    const entitiesMatch = testCase.expectedEntities.every(entity =>
      result.entities[entity as keyof typeof result.entities] !== undefined ||
      (entity === 'metrics' && result.entities.metrics?.length)
    );

    const success = intentMatch && entitiesMatch;

    console.log(`Test: "${testCase.input}"`);
    console.log(`Expected Intent: ${testCase.expectedIntent}, Got: ${result.type}`);
    console.log(`Expected Entities: ${testCase.expectedEntities.join(', ')}`);
    console.log(`Got Entities: ${Object.keys(result.entities).join(', ')}`);
    console.log(`Confidence: ${result.confidence.toFixed(2)}`);
    console.log(`Methods Used: ${result.methodsUsed.join(', ')}`);
    console.log(`Status: ${success ? '✅ PASS' : '❌ FAIL'}`);
    
    if (result.clarifications.length > 0) {
      console.log(`Clarifications needed: ${result.clarifications.join('; ')}`);
    }
    
    console.log('---\n');

    if (success) passed++;
    else failed++;
  }

  console.log(`\nResults: ${passed} passed, ${failed} failed out of ${testCases.length} tests`);
}

/**
 * Performance test: Rule-based vs. LLM
 */
export async function runPerformanceTest(): Promise<void> {
  console.log('=== Performance Comparison: Rule vs LLM ===\n');

  const testInput = '最近7天的良品率对比分析';
  const iterations = 5;

  // Rule-based performance
  console.log(`Testing rule-based matching (${iterations} iterations)...`);
  const ruleStart = performance.now();
  for (let i = 0; i < iterations; i++) {
    recognizeIntentSync(testInput);
  }
  const ruleEnd = performance.now();
  const ruleTime = ruleEnd - ruleStart;
  console.log(`Total time: ${ruleTime.toFixed(2)}ms`);
  console.log(`Average per call: ${(ruleTime / iterations).toFixed(2)}ms\n`);

  // LLM-based performance
  console.log(`Testing LLM-based matching (${iterations} iterations)...`);
  const llmStart = performance.now();
  for (let i = 0; i < iterations; i++) {
    await recognizeIntent(testInput);
  }
  const llmEnd = performance.now();
  const llmTime = llmEnd - llmStart;
  console.log(`Total time: ${llmTime.toFixed(2)}ms`);
  console.log(`Average per call: ${(llmTime / iterations).toFixed(2)}ms\n`);

  console.log(`Speed difference: LLM is ${(llmTime / ruleTime).toFixed(1)}x slower than rules`);
}

/**
 * Example: Using in a React component
 */
export async function exampleReactUsage(): Promise<void> {
  console.log('=== Example React Component Usage ===\n');

  const userInput = '查询本月各产线的良品率对比';
  
  console.log(`User input: "${userInput}"\n`);

  // For quick response, use sync version first
  const syncResult = recognizeIntentSync(userInput);
  console.log('Quick sync analysis:');
  console.log(`- Intent: ${syncResult.type}`);
  console.log(`- Confidence: ${syncResult.confidence.toFixed(2)}`);
  
  if (syncResult.confidence > 0.8) {
    console.log('- Decision: Use rule result (high confidence, low latency)\n');
  } else {
    console.log('- Decision: Calling LLM for confirmation...\n');
    
    // For better accuracy, use async version
    const asyncResult = await recognizeIntent(userInput);
    console.log('LLM confirmation result:');
    console.log(`- Intent: ${asyncResult.type}`);
    console.log(`- Confidence: ${asyncResult.confidence.toFixed(2)}`);
    console.log(`- Methods used: ${asyncResult.methodsUsed.join(', ')}`);
  }

  if (syncResult.clarifications.length > 0) {
    console.log('\nClarifications needed:');
    syncResult.clarifications.forEach(clarification => {
      console.log(`- ${clarification}`);
    });
  }
}

// Export test runner functions
export const tests = {
  runSyncTests,
  runAsyncTests,
  runPerformanceTest,
  exampleReactUsage
};
