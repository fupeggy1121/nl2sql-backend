/**
 * 部署 RPC 函数热修复到 Supabase
 * 通过 Service Role Key 直接执行 SQL
 */
const { createClient } = require('@supabase/supabase-js');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

const sb = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY);

async function deploy() {
  const sqlFile = path.join(__dirname, 'migrations', '003_hotfix_uuid_type_cast.sql');
  const sql = fs.readFileSync(sqlFile, 'utf-8');

  // Split by function boundaries and execute each CREATE OR REPLACE separately
  // (Supabase REST API may not support multiple statements in one call)
  const blocks = sql.split(/(?=-- \d+\.\s)/);

  for (const block of blocks) {
    const trimmed = block.trim();
    if (!trimmed || trimmed.startsWith('-- ===')) continue;

    // Extract function name for logging
    const fnMatch = trimmed.match(/CREATE OR REPLACE FUNCTION (\w+)/);
    const fnName = fnMatch ? fnMatch[1] : 'unknown';

    console.log(`Deploying: ${fnName}...`);

    // Use postgres REST endpoint or exec_sql if available
    const { data, error } = await sb.rpc('exec_sql', { sql: trimmed });
    if (error) {
      // Try alternative: use raw SQL through management API
      console.log(`  rpc('exec_sql') not available, trying direct fetch...`);

      const resp = await fetch(`${process.env.SUPABASE_URL}/rest/v1/rpc/exec_sql`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'apikey': process.env.SUPABASE_SERVICE_ROLE_KEY,
          'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_ROLE_KEY}`,
        },
        body: JSON.stringify({ sql: trimmed }),
      });

      if (!resp.ok) {
        console.log(`  Failed: ${resp.status} - need to run SQL in Supabase SQL Editor manually`);
        console.log(`  File: migrations/003_hotfix_uuid_type_cast.sql`);
        return false;
      }
    }
    console.log(`  OK`);
  }

  return true;
}

deploy().then(ok => {
  if (!ok) {
    console.log('\n⚠️  无法自动部署，请手动复制以下文件到 Supabase SQL Editor 执行:');
    console.log('   migrations/003_hotfix_uuid_type_cast.sql');
  } else {
    console.log('\n✅ 所有 RPC 函数已更新');
  }
}).catch(err => {
  console.error('Error:', err.message);
  console.log('\n请手动复制 migrations/003_hotfix_uuid_type_cast.sql 到 Supabase SQL Editor 执行');
});
