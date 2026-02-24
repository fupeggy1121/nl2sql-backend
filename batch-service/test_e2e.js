/**
 * 批次作业后端 — 端到端测试
 *
 * 使用方式:
 *   1. 确保 batch-service 正在运行: cd batch-service && npm run dev
 *   2. 运行测试: node test_e2e.js
 *
 * 测试分为两组:
 *   - 只读测试 (GET) — 不需要 RPC 函数，始终可用
 *   - 写操作测试 (POST) — 需要先在 Supabase SQL Editor 中部署 RPC 函数
 */

const BASE = process.env.BATCH_API_URL || 'http://localhost:3001';
const API = `${BASE}/api/batch`;

// ─── 测试框架 ─────────────────────────────────

let passed = 0;
let failed = 0;
let skipped = 0;
const results = [];

async function test(name, fn) {
  try {
    await fn();
    passed++;
    results.push({ name, status: 'PASS' });
    console.log(`  ✅ ${name}`);
  } catch (err) {
    if (err.message === 'SKIP') {
      skipped++;
      results.push({ name, status: 'SKIP', reason: err.reason });
      console.log(`  ⏭️  ${name} (skipped: ${err.reason})`);
    } else {
      failed++;
      results.push({ name, status: 'FAIL', error: err.message });
      console.log(`  ❌ ${name}`);
      console.log(`     ${err.message}`);
    }
  }
}

function skip(reason) {
  const err = new Error('SKIP');
  err.reason = reason;
  throw err;
}

function assert(cond, msg) {
  if (!cond) throw new Error(`Assertion failed: ${msg}`);
}

async function fetchJSON(path, options = {}) {
  const url = path.startsWith('http') ? path : API + path;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const body = await res.json();
  return { status: res.status, body };
}

// ─── 测试数据（来自真实数据库） ─────────────────

// 待出站批次 — 适合测试出站
const OUTSTATION_BATCH = {
  id: '527e34c6-8b7d-4dc4-a69d-6b9224165315',
  code: 'BATCHD7I17K',
  status: '待出站',
  subBatches: [
    { id: 'a02ccce2-1eb0-4b54-83ea-8decba9db628', sublot: 'BATCHD7I17K-SUB-01' },
    { id: 'ae775e93-ded4-4a6e-b975-dbd5499c8428', sublot: 'BATCHD7I17K-SUB-02' },
    { id: 'aa9f42b5-1d9b-42f8-a4df-4dc02ce4bcb0', sublot: 'BATCHD7I17K-SUB-03' },
  ],
};

// 待进站批次 (is_hold=true) — 适合测试进站被拒
const HOLD_BATCH = {
  id: 'aba03c67-3bf4-417c-b013-43f8f4d83c8e',
  code: 'BATCHQO20O3',
  status: '待进站',
  isHold: true,
};

// 加工中批次
const ACTIVE_BATCH = {
  id: '533e00f4-e470-480f-90c6-0b3612572bcd',
  code: 'BATCHX5VZPH',
  status: '加工中',
};

// ─── 只读测试 ─────────────────────────────────

async function runReadTests() {
  console.log('\n📖 只读测试 (GET endpoints)\n');

  await test('GET /health 返回 200', async () => {
    const { status, body } = await fetchJSON(`${BASE}/health`);
    assert(status === 200, `expected 200 got ${status}`);
    assert(body.status === 'ok', `expected ok got ${body.status}`);
  });

  await test('GET / 返回 API 文档', async () => {
    const { status, body } = await fetchJSON(`${BASE}/`);
    assert(status === 200, `expected 200 got ${status}`);
    assert(body.endpoints, 'missing endpoints field');
  });

  let batchList;
  await test('GET /list 返回批次列表', async () => {
    const { status, body } = await fetchJSON('/list?limit=5');
    assert(status === 200, `expected 200 got ${status}`);
    assert(body.success === true, `expected success=true`);
    assert(Array.isArray(body.data), 'data should be array');
    assert(body.data.length > 0, 'should have at least 1 batch');
    batchList = body.data;
  });

  await test('GET /list?status=加工中 筛选', async () => {
    const { status, body } = await fetchJSON('/list?status=' + encodeURIComponent('加工中') + '&limit=3');
    assert(status === 200, `expected 200 got ${status}`);
    assert(body.success === true, 'expected success=true');
    if (body.data.length > 0) {
      assert(body.data[0].status === '加工中', `expected 加工中 got ${body.data[0].status}`);
    }
  });

  await test('GET /:id 返回批次详情', async () => {
    const { status, body } = await fetchJSON(`/${OUTSTATION_BATCH.id}`);
    assert(status === 200, `expected 200 got ${status}`);
    assert(body.success === true, 'expected success=true');
    assert(body.data.batch, 'missing batch field');
    assert(body.data.batch.batch_code === OUTSTATION_BATCH.code,
      `expected ${OUTSTATION_BATCH.code} got ${body.data.batch.batch_code}`);
    assert(Array.isArray(body.data.subBatches), 'missing subBatches array');
  });

  await test('GET /:id 不存在的ID返回404', async () => {
    const { status, body } = await fetchJSON('/00000000-0000-0000-0000-000000000000');
    assert(status === 404, `expected 404 got ${status}`);
  });

  await test('GET /:id/wafers 返回晶圆数据', async () => {
    const stationCode = 'particleInspection02';
    const { status, body } = await fetchJSON(`/${OUTSTATION_BATCH.id}/wafers?stationCode=${stationCode}`);
    assert(status === 200, `expected 200 got ${status}`);
    assert(body.success === true, 'expected success=true');
    // wafers might be empty if station doesn't match, but structure should be valid
    assert(body.data !== undefined, 'missing data field');
  });

  await test('GET /:id/history 返回操作历史', async () => {
    const { status, body } = await fetchJSON(`/${OUTSTATION_BATCH.id}/history?limit=10`);
    assert(status === 200, `expected 200 got ${status}`);
    assert(body.success === true, 'expected success=true');
    assert(Array.isArray(body.data), 'data should be array');
  });
}

// ─── 写操作测试 ─────────────────────────────────

async function checkRPCAvailable() {
  // Quick test: call outstation with invalid batch_id — if RPC is working,
  // we'll get "Batch not found" instead of "function does not exist" or "operator does not exist"
  const { body } = await fetchJSON('/confirm-outstation', {
    method: 'POST',
    body: JSON.stringify({
      batchId: '00000000-0000-0000-0000-000000000001',
      waferResults: [],
      subBatches: [],
    }),
  });
  // If RPC works, error should be about "Batch not found" not "operator does not exist"
  const errMsg = body.error || '';
  if (errMsg.includes('operator does not exist') || errMsg.includes('function') || errMsg.includes('42883')) {
    return false;
  }
  return true;
}

async function runWriteTests() {
  console.log('\n✏️  写操作测试 (POST endpoints)\n');

  const rpcOK = await checkRPCAvailable();
  if (!rpcOK) {
    console.log('  ⚠️  RPC 函数尚未部署或存在类型错误');
    console.log('     请先在 Supabase SQL Editor 中执行:');
    console.log('     migrations/003_hotfix_uuid_type_cast.sql\n');
    console.log('     跳过所有写操作测试。\n');
    await test('RPC 函数可用性检查', () => skip('RPC functions not deployed'));
    return;
  }

  console.log('  ✅ RPC 函数已就绪\n');

  // --- 验证参数校验 ---

  await test('POST /confirm-outstation 缺少参数返回400', async () => {
    const { status, body } = await fetchJSON('/confirm-outstation', {
      method: 'POST',
      body: JSON.stringify({}),
    });
    assert(status === 400, `expected 400 got ${status}: ${JSON.stringify(body)}`);
  });

  await test('POST /confirm-instation 缺少参数返回400', async () => {
    const { status, body } = await fetchJSON('/confirm-instation', {
      method: 'POST',
      body: JSON.stringify({}),
    });
    assert(status === 400, `expected 400 got ${status}: ${JSON.stringify(body)}`);
  });

  await test('POST /confirm-split 缺少参数返回400', async () => {
    const { status, body } = await fetchJSON('/confirm-split', {
      method: 'POST',
      body: JSON.stringify({}),
    });
    assert(status === 400, `expected 400 got ${status}: ${JSON.stringify(body)}`);
  });

  await test('POST /confirm-merge 缺少参数返回400', async () => {
    const { status, body } = await fetchJSON('/confirm-merge', {
      method: 'POST',
      body: JSON.stringify({}),
    });
    assert(status === 400, `expected 400 got ${status}: ${JSON.stringify(body)}`);
  });

  // --- 验证不存在的批次 ---

  await test('POST /confirm-outstation 不存在的批次返回错误', async () => {
    const { status, body } = await fetchJSON('/confirm-outstation', {
      method: 'POST',
      body: JSON.stringify({
        batchId: '00000000-0000-0000-0000-000000000001',
        waferResults: [{ wafer_id: 'w1', type: 'GOOD', sublot_id: 's1' }],
        subBatches: [{ id: 's1', sublot_id: 's1' }],
      }),
    });
    assert(status >= 400, `expected error status got ${status}`);
    assert(body.error && body.error.includes('Batch not found'), `expected 'Batch not found' in: ${body.error}`);
  });

  // --- 验证业务规则 ---

  await test('POST /confirm-instation HOLD批次被拒绝', async () => {
    const { status, body } = await fetchJSON('/confirm-instation', {
      method: 'POST',
      body: JSON.stringify({
        batchId: HOLD_BATCH.id,
        subBatchIds: ['d56edb42-339f-4842-a679-8c26452fb56d'],
      }),
    });
    assert(status >= 400, `expected error status got ${status}`);
    assert(body.error && body.error.includes('HOLD'), `expected HOLD error in: ${body.error}`);
  });

  await test('POST /confirm-instation 非待进站状态被拒绝', async () => {
    // ACTIVE_BATCH is 加工中, not 待进站
    const { status, body } = await fetchJSON('/confirm-instation', {
      method: 'POST',
      body: JSON.stringify({
        batchId: ACTIVE_BATCH.id,
        subBatchIds: ['any-sub-batch-id'],
      }),
    });
    assert(status >= 400, `expected error status got ${status}`);
    assert(body.error, `expected error message, got: ${JSON.stringify(body)}`);
  });

  // --- 真实出站操作（使用待出站批次）---
  // ⚠️ 这会修改真实数据！仅在测试环境使用

  await test('POST /confirm-outstation 真实出站（待出站批次）', async () => {
    // Check current status first
    const { body: detail } = await fetchJSON(`/${OUTSTATION_BATCH.id}`);
    if (detail.data.batch.status !== '待出站') {
      skip(`Batch status is ${detail.data.batch.status}, not 待出站 (may have been changed by previous test)`);
    }

    const { status, body } = await fetchJSON('/confirm-outstation', {
      method: 'POST',
      body: JSON.stringify({
        batchId: OUTSTATION_BATCH.id,
        waferResults: [
          { wafer_id: 'w1', type: 'GOOD', sublot_id: OUTSTATION_BATCH.subBatches[0].sublot },
          { wafer_id: 'w2', type: 'GOOD', sublot_id: OUTSTATION_BATCH.subBatches[0].sublot },
          { wafer_id: 'w3', type: 'REJECT', sublot_id: OUTSTATION_BATCH.subBatches[1].sublot },
          { wafer_id: 'w4', type: 'GoodSample', sublot_id: OUTSTATION_BATCH.subBatches[1].sublot },
          { wafer_id: 'w5', type: 'GOOD', sublot_id: OUTSTATION_BATCH.subBatches[2].sublot },
        ],
        subBatches: OUTSTATION_BATCH.subBatches.map(s => ({
          id: s.id,
          sublot_id: s.sublot,
        })),
      }),
    });
    assert(status === 200, `expected 200 got ${status}: ${JSON.stringify(body)}`);
    assert(body.success === true, `expected success=true: ${JSON.stringify(body)}`);

    // Verify the batch is now 待进站
    const { body: after } = await fetchJSON(`/${OUTSTATION_BATCH.id}`);
    assert(after.data.batch.status === '待进站',
      `expected 待进站 got ${after.data.batch.status}`);
  });

  // Verify operation log was created
  await test('出站后操作日志已记录', async () => {
    const { body } = await fetchJSON(`/${OUTSTATION_BATCH.id}/history?limit=1`);
    assert(body.success === true, 'expected success=true');
    if (body.data.length > 0) {
      assert(body.data[0].operation_type === 'outstation',
        `expected outstation got ${body.data[0].operation_type}`);
      assert(body.data[0].batch_id === OUTSTATION_BATCH.id, 'batch_id mismatch');
    }
  });

  // Now test instation on the same batch (which is now 待进站)
  await test('POST /confirm-instation 出站后进站', async () => {
    const { body: detail } = await fetchJSON(`/${OUTSTATION_BATCH.id}`);
    if (detail.data.batch.status !== '待进站') {
      skip(`Batch status is ${detail.data.batch.status}`);
    }

    const subIds = detail.data.subBatches.map(s => s.id);

    const { status, body } = await fetchJSON('/confirm-instation', {
      method: 'POST',
      body: JSON.stringify({
        batchId: OUTSTATION_BATCH.id,
        subBatchIds: subIds,
        equipmentCode: 'EQ-TEST-001',
        equipmentName: '测试设备',
        operator: 'e2e-test',
      }),
    });
    assert(status === 200, `expected 200 got ${status}: ${JSON.stringify(body)}`);
    assert(body.success === true, `expected success=true`);

    // Verify
    const { body: after } = await fetchJSON(`/${OUTSTATION_BATCH.id}`);
    assert(after.data.batch.status === '加工中', `expected 加工中 got ${after.data.batch.status}`);
    assert(after.data.batch.equipment_code === 'EQ-TEST-001', 'equipment not set');
  });
}

// ─── 主流程 ─────────────────────────────────

async function main() {
  console.log('╔══════════════════════════════════════════════╗');
  console.log('║   批次作业后端 — 端到端测试                   ║');
  console.log('╚══════════════════════════════════════════════╝');
  console.log(`API: ${API}`);

  // Pre-check: is service running?
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(`${BASE}/health`, { signal: controller.signal });
    clearTimeout(timer);
    const hb = await res.json();
    console.log(`Service OK: uptime=${Math.round(hb.uptime)}s\n`);
  } catch (err) {
    console.error(`\n❌ 无法连接 batch-service (${err.message})，请先启动:`);
    console.error('   cd batch-service && npm run dev\n');
    process.exit(1);
  }

  await runReadTests();
  await runWriteTests();

  // ─── 汇总 ──────────────────────────────
  console.log('\n══════════════════════════════════════════════');
  console.log(`  ✅ Passed: ${passed}   ❌ Failed: ${failed}   ⏭️  Skipped: ${skipped}`);
  console.log('══════════════════════════════════════════════\n');

  if (failed > 0) {
    console.log('失败的测试:');
    results.filter(r => r.status === 'FAIL').forEach(r => {
      console.log(`  ❌ ${r.name}: ${r.error}`);
    });
    process.exit(1);
  }
}

main().catch(err => {
  console.error('Unexpected error:', err);
  process.exit(1);
});
