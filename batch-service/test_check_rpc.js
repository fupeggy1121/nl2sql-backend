const { createClient } = require('@supabase/supabase-js');
require('dotenv').config();

const sb = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY);

async function main() {
  // 1. Check all 4 RPC functions exist
  console.log('=== RPC Functions Status ===');
  const fns = [
    ['batch_confirm_outstation', { p_batch_id: 'test', p_wafer_results: '[]', p_sub_batches: '[]' }],
    ['batch_confirm_instation', { p_batch_id: 'test', p_sub_batch_ids: '{}' }],
    ['batch_confirm_split', { p_batch_id: 'test', p_split_config: '{}' }],
    ['batch_confirm_merge', { p_target_batch_id: 'test', p_source_sub_batch_ids: '{}' }],
  ];
  for (const [fn, params] of fns) {
    const { error } = await sb.rpc(fn, params);
    const msg = error ? error.code + ' - ' + error.message.slice(0, 100) : 'OK';
    console.log(`  ${fn}: ${msg}`);
  }

  // 2. Check batches.id column type
  const { data: colInfo } = await sb.rpc('execute_sql', {
    query: "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='batches' AND column_name='id'"
  });
  console.log('\n=== batches.id column type ===');
  console.log(JSON.stringify(colInfo));

  // 3. Get sub_batches for 待出站 batch
  const bid2 = '527e34c6-8b7d-4dc4-a69d-6b9224165315';
  const { data: subs2 } = await sb.from('sub_batches')
    .select('id, sub_batch_code, status, good_qty')
    .eq('batch_id', bid2).limit(3);
  console.log('\n=== Sub-batches for 待出站 batch ===');
  console.log(JSON.stringify(subs2, null, 2));

  // 4. Check wafer_carrier_contents
  if (subs2 && subs2[0]) {
    const { data: wcc } = await sb.from('wafer_carrier_contents')
      .select('id, wafer_id, sub_batch_id, carrier_id')
      .eq('sub_batch_id', subs2[0].id).limit(3);
    console.log('\n=== Wafer carrier contents ===');
    console.log(JSON.stringify(wcc, null, 2));
  }

  // 5. Check batch_operation_logs table
  const { data: logs, error: logErr } = await sb.from('batch_operation_logs').select('id').limit(1);
  console.log('\n=== batch_operation_logs ===');
  console.log(logErr ? 'NOT EXISTS: ' + logErr.message : 'EXISTS, rows: ' + (logs ? logs.length : 0));
}

main().catch(console.error);
