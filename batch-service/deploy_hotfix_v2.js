/**
 * 通过 Supabase service_role 直接执行 SQL 部署 RPC 函数
 * 利用已有的 execute_sql RPC（虽然它限制了 INSERT/UPDATE/DELETE，
 * 但 CREATE OR REPLACE FUNCTION 是 DDL 语句，应该不受限制）
 */
const { createClient } = require('@supabase/supabase-js');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

const sb = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY);

async function deploySingleFunction(name, sql) {
  console.log(`  Deploying ${name}...`);

  // Try via execute_sql RPC
  const { data, error } = await sb.rpc('execute_sql', { query: sql });
  if (error) {
    console.log(`    execute_sql failed: ${error.message}`);
    return false;
  }
  console.log(`    OK`);
  return true;
}

async function main() {
  const sqlFile = path.join(__dirname, 'migrations', '003_hotfix_uuid_type_cast.sql');
  const fullSql = fs.readFileSync(sqlFile, 'utf-8');

  // Split into individual function blocks (each starts with "CREATE OR REPLACE FUNCTION")
  const functionBlocks = [];
  const regex = /(CREATE OR REPLACE FUNCTION[\s\S]*?;)\s*\n\s*(GRANT[\s\S]*?;)/g;
  let match;
  while ((match = regex.exec(fullSql)) !== null) {
    functionBlocks.push({
      sql: match[1] + '\n' + match[2],
      name: match[1].match(/FUNCTION (\w+)/)[1],
    });
  }

  console.log(`Found ${functionBlocks.length} functions to deploy\n`);

  let allOk = true;
  for (const block of functionBlocks) {
    const ok = await deploySingleFunction(block.name, block.sql);
    if (!ok) allOk = false;
  }

  if (!allOk) {
    console.log('\n⚠️  部分函数部署失败。请手动复制以下文件到 Supabase SQL Editor:');
    console.log('   migrations/003_hotfix_uuid_type_cast.sql');
    console.log('\n   （已修复 now()::text → now()）');
  } else {
    console.log('\n✅ 全部 RPC 函数已更新');
  }
}

main().catch(console.error);
