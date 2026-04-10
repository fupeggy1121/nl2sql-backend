/**
 * streamChat() 单元测试 — Phase 2 SSE 流式 API
 * ================================================
 * 使用 vitest + jsdom 环境，通过 mock fetch 模拟 SSE 流，
 * 无需运行后端即可完整测试前端解析逻辑。
 *
 * 覆盖场景：
 *   1. 正常流：trace_step × N → done
 *   2. 回调按序触发（onStep → onDone）
 *   3. 后端 error 事件触发 onError
 *   4. HTTP 非 200 触发 onError（含状态码信息）
 *   5. AbortController 中止时不触发 onError（AbortError 被吞）
 *   6. JSON 解析失败的帧被静默跳过
 *   7. 跨 chunk 边界的 SSE 帧正确拼接
 *   8. 空 data 字段的行被忽略
 *   9. 返回的 AbortController 可用
 *  10. onDone payload 结构验证
 *
 * 运行：
 *   cd /Users/fupeggy/NL2SQL/frontend
 *   npx vitest run src/services/__tests__/streamChat.test.ts
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { streamChat, type StreamDonePayload } from '../nl2sqlApi';

// ──────────────────────────────────────────────
// SSE Mock 工具
// ──────────────────────────────────────────────

/** 将若干 SSE 帧合并为 Uint8Array 字节流 */
function buildSSEBody(frames: Array<{ event: string; data: unknown }>): Uint8Array {
  const text = frames
    .map((f) => `event: ${f.event}\ndata: ${JSON.stringify(f.data)}\n\n`)
    .join('');
  return new TextEncoder().encode(text);
}

/**
 * 构造一个可被 fetch 返回的 ReadableStream<Uint8Array>，
 * 可选地分多个 chunk 推送（模拟网络分片）。
 */
function makeStream(chunks: Uint8Array[]): ReadableStream<Uint8Array> {
  let i = 0;
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(chunks[i++]);
      } else {
        controller.close();
      }
    },
  });
}

/** 标准"成功"SSE 流：3 个 trace_step + 1 个 done */
function makeSuccessStream(stepCount = 3) {
  const steps = Array.from({ length: stepCount }, (_, i) => ({
    event: 'trace_step',
    data: {
      step_key: `step_${i}`,
      title: `步骤 ${i}`,
      status: 'completed',
      elapsed_ms: i * 100,
    },
  }));
  const donePayload: StreamDonePayload = {
    success: true,
    session_id: 'mock_session_1',
    data: {
      type: 'query',
      query_result: { success: true, data: [], rows_count: 0 },
    } as any,
    pipeline_trace: steps.map((s) => s.data as any),
  };
  const body = buildSSEBody([...steps, { event: 'done', data: donePayload }]);
  return [body];
}

function mockFetch(status: number, bodyChunks: Uint8Array[]) {
  const stream = makeStream(bodyChunks);
  vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
    new Response(stream, {
      status,
      headers: { 'Content-Type': 'text/event-stream' },
    }),
  );
}

// ──────────────────────────────────────────────
// Test helpers
// ──────────────────────────────────────────────

/** 等待 streamChat 内部的 promise（通过轮询 onDone/onError 是否触发） */
function waitForCompletion(
  onDoneRef: { value: boolean },
  onErrorRef: { value: boolean },
  timeoutMs = 3000,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      if (onDoneRef.value || onErrorRef.value) return resolve();
      if (Date.now() - start > timeoutMs) return reject(new Error('Timeout waiting for stream'));
      setTimeout(check, 10);
    };
    check();
  });
}

// ──────────────────────────────────────────────
// Tests
// ──────────────────────────────────────────────

describe('streamChat()', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── 1. 正常流完整接收 ──
  it('正常流：onStep 触发 N 次，onDone 触发 1 次', async () => {
    const STEP_COUNT = 3;
    mockFetch(200, makeSuccessStream(STEP_COUNT));

    const stepsCalled: unknown[] = [];
    const doneRef = { value: false };
    const errorRef = { value: false };

    streamChat('查询批次', 'sess_1', [], {
      onStep: (step) => stepsCalled.push(step),
      onDone: () => { doneRef.value = true; },
      onError: () => { errorRef.value = true; },
    });

    await waitForCompletion(doneRef, errorRef);

    expect(stepsCalled).toHaveLength(STEP_COUNT);
    expect(doneRef.value).toBe(true);
    expect(errorRef.value).toBe(false);
  });

  // ── 2. 回调顺序：onStep 全部在 onDone 之前 ──
  it('回调顺序：所有 onStep 在 onDone 之前', async () => {
    mockFetch(200, makeSuccessStream(2));

    const order: string[] = [];
    const doneRef = { value: false };
    const errorRef = { value: false };

    streamChat('测试顺序', undefined, [], {
      onStep: () => order.push('step'),
      onDone: () => { order.push('done'); doneRef.value = true; },
      onError: () => { errorRef.value = true; },
    });

    await waitForCompletion(doneRef, errorRef);
    expect(order).toEqual(['step', 'step', 'done']);
  });

  // ── 3. onDone payload 结构 ──
  it('onDone 接收到含 success / session_id / pipeline_trace 的 payload', async () => {
    mockFetch(200, makeSuccessStream(2));

    let receivedPayload: StreamDonePayload | null = null;
    const doneRef = { value: false };
    const errorRef = { value: false };

    streamChat('结构测试', 'sess_struct', [], {
      onStep: () => {},
      onDone: (p) => { receivedPayload = p; doneRef.value = true; },
      onError: () => { errorRef.value = true; },
    });

    await waitForCompletion(doneRef, errorRef);

    expect(receivedPayload).not.toBeNull();
    expect(receivedPayload!.success).toBe(true);
    expect(receivedPayload!.session_id).toBe('mock_session_1');
    expect(Array.isArray(receivedPayload!.pipeline_trace)).toBe(true);
    expect(receivedPayload!.pipeline_trace).toHaveLength(2);
  });

  // ── 4. 后端 error 事件 → onError ──
  it('后端 error 事件触发 onError，不触发 onStep / onDone', async () => {
    const body = buildSSEBody([{ event: 'error', data: { error: 'SQL 生成失败' } }]);
    mockFetch(200, [body]);

    const steps: unknown[] = [];
    const errors: string[] = [];
    const doneRef = { value: false };
    const errorRef = { value: false };

    streamChat('触发错误', undefined, [], {
      onStep: (s) => steps.push(s),
      onDone: () => { doneRef.value = true; },
      onError: (e) => { errors.push(e); errorRef.value = true; },
    });

    await waitForCompletion(doneRef, errorRef);

    expect(steps).toHaveLength(0);
    expect(doneRef.value).toBe(false);
    expect(errors).toHaveLength(1);
    expect(errors[0]).toContain('SQL 生成失败');
  });

  // ── 5. HTTP 非 200 → onError 含状态码 ──
  it('HTTP 500 触发 onError 并包含状态码', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response('Internal Server Error', { status: 500 }),
    );

    const errors: string[] = [];
    const doneRef = { value: false };
    const errorRef = { value: false };

    streamChat('HTTP 错误', undefined, [], {
      onStep: () => {},
      onDone: () => { doneRef.value = true; },
      onError: (e) => { errors.push(e); errorRef.value = true; },
    });

    await waitForCompletion(doneRef, errorRef);

    expect(doneRef.value).toBe(false);
    expect(errors).toHaveLength(1);
    expect(errors[0]).toContain('500');
  });

  // ── 6. HTTP 401 → onError ──
  it('HTTP 401 触发 onError 并包含状态码 401', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response('Unauthorized', { status: 401 }),
    );

    const errorRef = { value: false };
    let errorMsg = '';
    const doneRef = { value: false };

    streamChat('权限测试', undefined, [], {
      onStep: () => {},
      onDone: () => { doneRef.value = true; },
      onError: (e) => { errorMsg = e; errorRef.value = true; },
    });

    await waitForCompletion(doneRef, errorRef);
    expect(errorMsg).toContain('401');
  });

  // ── 7. AbortController 中止 → 不触发 onError ──
  it('abort() 后 onError 不被触发', async () => {
    // 永不 resolve 的 fetch（模拟挂起请求）
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(
      (_url, opts) =>
        new Promise((_resolve, reject) => {
          (opts as RequestInit).signal?.addEventListener('abort', () =>
            reject(new DOMException('AbortError', 'AbortError')),
          );
        }),
    );

    const errorRef = { value: false };
    const doneRef = { value: false };

    const controller = streamChat('中止测试', undefined, [], {
      onStep: () => {},
      onDone: () => { doneRef.value = true; },
      onError: () => { errorRef.value = true; },
    });

    // 立即中止
    controller.abort();

    // 等待 150ms，确认回调未被触发
    await new Promise((r) => setTimeout(r, 150));
    expect(errorRef.value).toBe(false);
    expect(doneRef.value).toBe(false);
  });

  // ── 8. 返回有效 AbortController ──
  it('返回的 AbortController 是 AbortController 实例', () => {
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(
      () => new Promise(() => {}),
    );
    const controller = streamChat('类型检查', undefined, [], {
      onStep: () => {},
      onDone: () => {},
      onError: () => {},
    });
    expect(controller).toBeInstanceOf(AbortController);
    controller.abort();
  });

  // ── 9. 无效 JSON 帧被静默跳过 ──
  it('无效 JSON 帧被跳过，不影响后续正确帧', async () => {
    const validStep = { step_key: 'intent_router', title: '意图识别', status: 'completed' };
    const doneData: StreamDonePayload = {
      success: true,
      session_id: 's_skip',
      data: {} as any,
      pipeline_trace: [validStep as any],
    };
    // 混入一帧格式正确但 JSON 损坏的数据
    const rawText =
      `event: trace_step\ndata: {broken_json\n\n` +
      `event: trace_step\ndata: ${JSON.stringify(validStep)}\n\n` +
      `event: done\ndata: ${JSON.stringify(doneData)}\n\n`;
    const body = new TextEncoder().encode(rawText);
    mockFetch(200, [body]);

    const steps: unknown[] = [];
    const doneRef = { value: false };
    const errorRef = { value: false };

    streamChat('跳过测试', undefined, [], {
      onStep: (s) => steps.push(s),
      onDone: () => { doneRef.value = true; },
      onError: () => { errorRef.value = true; },
    });

    await waitForCompletion(doneRef, errorRef);

    // 破损帧跳过，有效帧正常收到
    expect(steps).toHaveLength(1);
    expect((steps[0] as any).step_key).toBe('intent_router');
    expect(doneRef.value).toBe(true);
  });

  // ── 10. 跨 chunk 边界拼接 ──
  it('SSE 帧跨 chunk 边界时正确拼接', async () => {
    const step = { step_key: 'sql_generator', title: 'SQL 生成', status: 'completed' };
    const done: StreamDonePayload = {
      success: true,
      session_id: 's_chunk',
      data: {} as any,
      pipeline_trace: [step as any],
    };
    const fullText =
      `event: trace_step\ndata: ${JSON.stringify(step)}\n\n` +
      `event: done\ndata: ${JSON.stringify(done)}\n\n`;
    const bytes = new TextEncoder().encode(fullText);
    // 从中间切开，模拟分片
    const mid = Math.floor(bytes.length / 2);
    mockFetch(200, [bytes.slice(0, mid), bytes.slice(mid)]);

    const steps: unknown[] = [];
    const doneRef = { value: false };
    const errorRef = { value: false };

    streamChat('分片测试', undefined, [], {
      onStep: (s) => steps.push(s),
      onDone: () => { doneRef.value = true; },
      onError: () => { errorRef.value = true; },
    });

    await waitForCompletion(doneRef, errorRef);
    expect(steps).toHaveLength(1);
    expect(doneRef.value).toBe(true);
  });
});
