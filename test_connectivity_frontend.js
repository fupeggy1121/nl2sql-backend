/**
 * 前端服务联通性测试脚本
 * 用于在浏览器中测试：
 * 1. 前端到后端的通信
 * 2. 后端API响应
 * 3. 数据处理和显示
 */

// 配置
const API_CONFIG = {
  development: 'http://localhost:5000',
  production: 'https://your-production-api.com',
  tunnel: process.env.REACT_APP_API_URL || 'http://localhost:5000',
};

const API_URL = API_CONFIG.tunnel || API_CONFIG.development;

// 颜色输出辅助函数
const log = {
  success: (msg) => console.log('%c✅ ' + msg, 'color: #4CAF50; font-weight: bold;'),
  error: (msg) => console.log('%c❌ ' + msg, 'color: #f44336; font-weight: bold;'),
  info: (msg) => console.log('%cℹ️  ' + msg, 'color: #2196F3; font-weight: bold;'),
  warning: (msg) => console.log('%c⚠️  ' + msg, 'color: #FF9800; font-weight: bold;'),
  header: (msg) => console.log('%c\n═══ ' + msg + ' ═══\n', 'color: #9C27B0; font-weight: bold; font-size: 14px;'),
};

/**
 * 测试1: 后端健康检查
 */
async function testBackendHealth() {
  log.header('后端服务健康检查');
  
  try {
    const response = await fetch(`${API_URL}/api/query/health`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    
    if (response.ok) {
      const data = await response.json();
      log.success(`后端服务正常: ${JSON.stringify(data)}`);
      return true;
    } else {
      log.error(`后端服务异常 (状态码: ${response.status})`);
      return false;
    }
  } catch (error) {
    log.error(`后端健康检查失败: ${error.message}`);
    return false;
  }
}

/**
 * 测试2: NL2SQL转换端点
 */
async function testNL2SQLConversion() {
  log.header('NL2SQL转换端点测试');
  
  const testQueries = [
    '查询所有用户',
    '显示wafers表的前100条数据',
    '返回wafers表的前300条数据',
  ];
  
  let passed = 0;
  
  for (const query of testQueries) {
    try {
      log.info(`测试查询: ${query}`);
      
      const response = await fetch(`${API_URL}/api/query/nl-to-sql`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ natural_language: query }),
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          log.success(`✓ 生成SQL: ${data.sql}`);
          passed++;
        } else {
          log.warning(`⚠ 转换失败: ${data.error}`);
        }
      } else {
        log.error(`❌ 状态码 ${response.status}`);
      }
    } catch (error) {
      log.error(`查询 "${query}" 失败: ${error.message}`);
    }
  }
  
  log.info(`NL2SQL测试通过: ${passed}/${testQueries.length}`);
  return passed === testQueries.length;
}

/**
 * 测试3: 数据库查询执行
 */
async function testDatabaseQuery() {
  log.header('数据库查询执行测试');
  
  try {
    const response = await fetch(`${API_URL}/api/query/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sql: 'SELECT * FROM wafers LIMIT 5',
      }),
    });
    
    if (response.ok) {
      const data = await response.json();
      log.success(`查询成功: 返回 ${data.data?.length || 0} 条记录`);
      if (data.data && data.data.length > 0) {
        log.info(`样本数据: ${JSON.stringify(data.data[0])}`);
      }
      return true;
    } else {
      log.error(`查询失败 (状态码: ${response.status})`);
      return false;
    }
  } catch (error) {
    log.error(`数据库查询测试失败: ${error.message}`);
    return false;
  }
}

/**
 * 测试4: CORS跨域测试
 */
async function testCORS() {
  log.header('CORS跨域配置测试');
  
  try {
    const response = await fetch(`${API_URL}/api/query/health`, {
      method: 'OPTIONS',
      headers: {
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Content-Type',
      },
    });
    
    const corsHeaders = {
      'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
      'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
      'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers'),
    };
    
    if (corsHeaders['Access-Control-Allow-Origin']) {
      log.success(`CORS配置正确:`);
      Object.entries(corsHeaders).forEach(([key, value]) => {
        if (value) log.info(`  ${key}: ${value}`);
      });
      return true;
    } else {
      log.warning('未检测到CORS头');
      return false;
    }
  } catch (error) {
    log.error(`CORS测试失败: ${error.message}`);
    return false;
  }
}

/**
 * 测试5: 网络连接速度
 */
async function testNetworkLatency() {
  log.header('网络连接速度测试');
  
  try {
    const startTime = performance.now();
    
    await fetch(`${API_URL}/api/query/health`);
    
    const endTime = performance.now();
    const latency = (endTime - startTime).toFixed(2);
    
    if (latency < 200) {
      log.success(`网络延迟: ${latency}ms (优秀)`);
    } else if (latency < 500) {
      log.info(`网络延迟: ${latency}ms (正常)`);
    } else {
      log.warning(`网络延迟: ${latency}ms (较高)`);
    }
    
    return true;
  } catch (error) {
    log.error(`网络速度测试失败: ${error.message}`);
    return false;
  }
}

/**
 * 测试6: API错误处理
 */
async function testErrorHandling() {
  log.header('API错误处理测试');
  
  try {
    // 测试无效的SQL
    const response = await fetch(`${API_URL}/api/query/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sql: 'INVALID SQL QUERY',
      }),
    });
    
    if (!response.ok) {
      const data = await response.json();
      log.success(`错误处理正常: ${data.error || '返回错误响应'}`);
      return true;
    } else {
      log.warning('错误处理可能有问题: 无效SQL未被捕获');
      return false;
    }
  } catch (error) {
    log.success(`错误被正确捕获: ${error.message}`);
    return true;
  }
}

/**
 * 测试7: 页面加载性能
 */
function testPagePerformance() {
  log.header('页面加载性能测试');
  
  if (window.performance && window.performance.timing) {
    const timing = window.performance.timing;
    const metrics = {
      'DNS解析': timing.domainLookupEnd - timing.domainLookupStart,
      'TCP连接': timing.connectEnd - timing.connectStart,
      '首字节时间': timing.responseStart - timing.requestStart,
      '资源加载': timing.responseEnd - timing.responseStart,
      '页面加载': timing.loadEventEnd - timing.navigationStart,
    };
    
    Object.entries(metrics).forEach(([key, value]) => {
      if (value > 0) {
        if (value < 100) {
          log.success(`${key}: ${value}ms`);
        } else if (value < 500) {
          log.info(`${key}: ${value}ms`);
        } else {
          log.warning(`${key}: ${value}ms (较高)`);
        }
      }
    });
    
    return true;
  } else {
    log.warning('浏览器不支持Performance API');
    return false;
  }
}

/**
 * 运行所有测试
 */
async function runAllTests() {
  console.clear();
  
  console.log('%c╔════════════════════════════════════════════════════════╗', 'color: #9C27B0; font-weight: bold;');
  console.log('%c║                                                        ║', 'color: #9C27B0; font-weight: bold;');
  console.log('%c║      NL2SQL 前端服务联通性测试套件                       ║', 'color: #9C27B0; font-weight: bold; font-size: 14px;');
  console.log('%c║      API地址: ' + API_URL.padEnd(41) + '║', 'color: #9C27B0; font-weight: bold;');
  console.log('%c║      时间: ' + new Date().toLocaleString().padEnd(44) + '║', 'color: #9C27B0; font-weight: bold;');
  console.log('%c║                                                        ║', 'color: #9C27B0; font-weight: bold;');
  console.log('%c╚════════════════════════════════════════════════════════╝', 'color: #9C27B0; font-weight: bold;');
  
  const results = {};
  
  // 运行所有测试
  results['后端健康检查'] = await testBackendHealth();
  results['NL2SQL转换'] = await testNL2SQLConversion();
  results['数据库查询'] = await testDatabaseQuery();
  results['CORS配置'] = await testCORS();
  results['网络延迟'] = await testNetworkLatency();
  results['错误处理'] = await testErrorHandling();
  results['页面性能'] = testPagePerformance();
  
  // 测试总结
  log.header('测试总结');
  
  Object.entries(results).forEach(([testName, result]) => {
    const status = result ? '✅ PASS' : '❌ FAIL';
    console.log(status + ' - ' + testName);
  });
  
  // 计算通过率
  const passed = Object.values(results).filter(Boolean).length;
  const total = Object.keys(results).length;
  const successRate = ((passed / total) * 100).toFixed(0);
  
  console.log(`\n总体通过率: ${passed}/${total} (${successRate}%)\n`);
  
  if (successRate == 100) {
    log.success('所有测试通过！系统运行正常 🎉');
  } else if (successRate >= 75) {
    log.warning('大部分测试通过，但存在些许问题');
  } else {
    log.error('存在多个测试失败，请检查配置');
  }
  
  // 返回结果
  return results;
}

// 导出函数供外部使用
window.TestConnectivity = {
  runAllTests,
  testBackendHealth,
  testNL2SQLConversion,
  testDatabaseQuery,
  testCORS,
  testNetworkLatency,
  testErrorHandling,
  testPagePerformance,
};

// 自动运行（如果直接包含此脚本）
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    console.log('💡 提示: 在浏览器控制台中运行 TestConnectivity.runAllTests() 来测试服务联通性');
  });
} else {
  console.log('💡 提示: 在浏览器控制台中运行 TestConnectivity.runAllTests() 来测试服务联通性');
}
