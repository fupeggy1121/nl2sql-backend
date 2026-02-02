/**
 * 📡 NL2SQL API 客户端 - nl2sqlApi.js
 * 
 * 使用说明：
 * 1. 复制此文件到你的 Bolt 项目的 src/services/ 目录
 * 2. 确保后端 URL 正确
 * 3. 在需要的组件中导入使用
 * 
 * 例如：
 * import nl2sqlApi from './services/nl2sqlApi';
 * const result = await nl2sqlApi.checkConnection();
 */

// ⚠️ 重要：更新此 URL 为你的后端地址
// 当前配置的是 Render 部署的后端
const API_BASE_URL = 'https://nl2sql-backend-amok.onrender.com/api/query';

// 如果在本地开发，可以切换到本地地址
// const API_BASE_URL = 'http://localhost:8000/api/query';

/**
 * 检查数据库连接状态
 * @returns {Promise<Object>} 连接状态信息
 */
export const checkConnection = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      console.warn(`❌ Health check failed with status ${response.status}`);
      return {
        connected: false,
        status: 'error',
        error: `HTTP ${response.status}`,
      };
    }

    const data = await response.json();
    
    // 只要后端响应且 status 为 healthy 就认为连接成功
    // supabase 连接可能失败，但不影响 NL2SQL 转换功能
    const isConnected = data.status === 'healthy';
    
    return {
      connected: isConnected,
      status: data.status,
      supabase: data.supabase,
      tables: data.tables || [],
    };
  } catch (error) {
    console.error('❌ Connection check failed:', error);
    return {
      connected: false,
      status: 'error',
      error: error.message,
    };
  }
};

/**
 * 执行自然语言查询
 * 将自然语言转换为 SQL 并执行
 * 
 * @param {string} naturalLanguage - 自然语言查询，例如 "查询所有用户"
 * @returns {Promise<Object>} 查询结果
 * 
 * 返回格式：
 * {
 *   success: true,
 *   sql: "SELECT * FROM users;",
 *   data: [...],  // 查询返回的数据
 *   count: 100,   // 返回的记录数
 *   error: null
 * }
 */
export const executeNLQuery = async (naturalLanguage) => {
  if (!naturalLanguage || !naturalLanguage.trim()) {
    return {
      success: false,
      error: '查询不能为空',
    };
  }

  try {
    const response = await fetch(`${API_BASE_URL}/nl-execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        natural_language: naturalLanguage.trim(),
      }),
    });

    if (!response.ok) {
      console.warn(`❌ Query execution failed with status ${response.status}`);
      return {
        success: false,
        error: `HTTP ${response.status}`,
      };
    }

    return await response.json();
  } catch (error) {
    console.error('❌ Query execution failed:', error);
    return {
      success: false,
      error: error.message,
    };
  }
};

/**
 * 将自然语言转换为 SQL（仅转换，不执行）
 * 用于在执行前预览 SQL
 * 
 * @param {string} naturalLanguage - 自然语言查询
 * @returns {Promise<Object>} 转换结果
 * 
 * 返回格式：
 * {
 *   success: true,
 *   sql: "SELECT * FROM users;",
 *   natural_language: "查询所有用户",
 *   message: "Conversion successful"
 * }
 */
export const convertNLToSQL = async (naturalLanguage) => {
  if (!naturalLanguage || !naturalLanguage.trim()) {
    return {
      success: false,
      error: '查询不能为空',
    };
  }

  try {
    const response = await fetch(`${API_BASE_URL}/nl-to-sql`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        natural_language: naturalLanguage.trim(),
      }),
    });

    if (!response.ok) {
      console.warn(`❌ NL to SQL conversion failed with status ${response.status}`);
      return {
        success: false,
        error: `HTTP ${response.status}`,
      };
    }

    return await response.json();
  } catch (error) {
    console.error('❌ NL to SQL conversion failed:', error);
    return {
      success: false,
      error: error.message,
    };
  }
};

/**
 * 获取数据库 Schema
 * 获取所有表的结构信息
 * 
 * @returns {Promise<Object>} 数据库 Schema 信息
 */
export const getSchema = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/supabase/schema`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      return {
        success: false,
        error: `HTTP ${response.status}`,
      };
    }

    return await response.json();
  } catch (error) {
    console.error('❌ Failed to get schema:', error);
    return {
      success: false,
      error: error.message,
    };
  }
};

/**
 * 检查 Supabase 连接
 * 
 * @returns {Promise<Object>} 连接状态
 */
export const checkSupabaseConnection = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/supabase/connection`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      return {
        success: false,
        error: `HTTP ${response.status}`,
      };
    }

    return await response.json();
  } catch (error) {
    console.error('❌ Supabase connection check failed:', error);
    return {
      success: false,
      error: error.message,
    };
  }
};

/**
 * 调试工具：打印当前 API 配置
 */
export const debugApiConfig = () => {
  console.group('📡 NL2SQL API 配置');
  console.log('API Base URL:', API_BASE_URL);
  console.log('完整端点:');
  console.log('  - 健康检查:', `${API_BASE_URL}/health`);
  console.log('  - NL 执行:', `${API_BASE_URL}/nl-execute`);
  console.log('  - NL 转 SQL:', `${API_BASE_URL}/nl-to-sql`);
  console.log('  - Schema:', `${API_BASE_URL}/supabase/schema`);
  console.log('  - Supabase 连接:', `${API_BASE_URL}/supabase/connection`);
  console.groupEnd();
};

/**
 * 导出为默认对象，便于导入使用
 */
const nl2sqlApi = {
  checkConnection,
  executeNLQuery,
  convertNLToSQL,
  getSchema,
  checkSupabaseConnection,
  debugApiConfig,
};

export default nl2sqlApi;
