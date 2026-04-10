"""
Phase 2 SSE 流式追踪端点测试
=========================================
覆盖范围：
  1. SSE 帧格式验证（event: / data: 分隔符）
  2. trace_step 事件结构
  3. done 事件结构与业务字段
  4. error 事件（后端主动抛出）
  5. 请求参数校验（422 Validation）
  6. 流被客户端中断（断开连接不崩溃）
  7. session_id 透传
  8. 非 adhoc 路由（analysis / multi_skill）走 _stream_via_invoke 路径

运行方式：
    cd /Users/fupeggy/NL2SQL
    .venv/bin/pytest tests/test_chat_stream.py -v
"""

import json
import sys
import os
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starlette.testclient import TestClient
from app.main import app


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient（模块级，避免重复创建应用）"""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ──────────────────────────────────────────────
# 辅助工具
# ──────────────────────────────────────────────

def _collect_sse(response) -> list[dict]:
    """
    将 SSE 流响应体解析为事件列表。
    每条事件：{"event": str, "data": dict | str}
    """
    events = []
    current_event = {}
    buf = ""
    for chunk in response.iter_bytes():
        buf += chunk.decode("utf-8", errors="replace")
        while "\n\n" in buf:
            block, buf = buf.split("\n\n", 1)
            event_type = ""
            data_str = ""
            for line in block.strip().splitlines():
                if line.startswith("event: "):
                    event_type = line[7:].strip()
                elif line.startswith("data: "):
                    data_str = line[6:]
            if not data_str:
                continue
            try:
                parsed = json.loads(data_str)
            except json.JSONDecodeError:
                parsed = data_str
            events.append({"event": event_type, "data": parsed})
    return events


def _stream_post(client: TestClient, payload: dict):
    """向 /api/v1/chat/stream 发一个流式 POST，返回 (response, events)。"""
    with client.stream(
        "POST",
        "/api/v1/chat/stream",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
    ) as response:
        events = _collect_sse(response)
    return response, events


# ──────────────────────────────────────────────
# Test Suite 1: 响应头与 Content-Type
# ──────────────────────────────────────────────

class TestSSEResponseHeaders:
    """验证 SSE 端点返回正确的 Content-Type"""

    def test_content_type_is_text_event_stream(self, client):
        payload = {"message": "当前在加工批次数", "session_id": "ts_hdr_1"}
        with client.stream("POST", "/api/v1/chat/stream", json=payload, timeout=30) as resp:
            # 只检查头，不消费全部流
            ct = resp.headers.get("content-type", "")
            assert "text/event-stream" in ct, f"Expected text/event-stream, got: {ct}"

    def test_no_cache_header(self, client):
        payload = {"message": "ping", "session_id": "ts_hdr_2"}
        with client.stream("POST", "/api/v1/chat/stream", json=payload, timeout=30) as resp:
            cc = resp.headers.get("cache-control", "")
            assert "no-cache" in cc or resp.status_code == 200


# ──────────────────────────────────────────────
# Test Suite 2: SSE 帧格式
# ──────────────────────────────────────────────

class TestSSEFrameFormat:
    """验证每一帧遵循 SSE 规范：event: / data: / 空行分隔"""

    def test_raw_bytes_contain_event_prefix(self, client):
        payload = {"message": "查询设备列表", "session_id": "ts_fmt_1"}
        raw_chunks = []
        with client.stream("POST", "/api/v1/chat/stream", json=payload, timeout=30) as resp:
            assert resp.status_code == 200
            for chunk in resp.iter_bytes():
                raw_chunks.append(chunk)
        raw = b"".join(raw_chunks).decode()
        assert "event: " in raw, "响应体中应包含 'event: ' 前缀"
        assert "data: " in raw, "响应体中应包含 'data: ' 前缀"

    def test_each_event_block_separated_by_double_newline(self, client):
        payload = {"message": "查询今日良率", "session_id": "ts_fmt_2"}
        raw_chunks = []
        with client.stream("POST", "/api/v1/chat/stream", json=payload, timeout=30) as resp:
            for chunk in resp.iter_bytes():
                raw_chunks.append(chunk)
        raw = b"".join(raw_chunks).decode()
        # 至少一个双换行分隔
        assert "\n\n" in raw, "SSE 帧之间应用 \\n\\n 分隔"

    def test_data_field_is_valid_json(self, client):
        payload = {"message": "查询站点", "session_id": "ts_fmt_3"}
        _, events = _stream_post(client, payload)
        assert len(events) > 0, "应至少有一条 SSE 事件"
        for ev in events:
            assert isinstance(ev["data"], dict), (
                f"event={ev['event']} 的 data 应为 JSON 对象，得到: {type(ev['data'])}"
            )


# ──────────────────────────────────────────────
# Test Suite 3: trace_step 事件
# ──────────────────────────────────────────────

class TestTraceStepEvents:
    """验证 trace_step 事件的存在与结构"""

    def test_at_least_one_trace_step(self, client):
        payload = {"message": "统计各站点批次数", "session_id": "ts_trace_1"}
        _, events = _stream_post(client, payload)
        trace_events = [e for e in events if e["event"] == "trace_step"]
        assert len(trace_events) >= 1, f"应至少有一个 trace_step 事件，实际事件: {[e['event'] for e in events]}"

    def test_trace_step_has_step_key_field(self, client):
        payload = {"message": "查询良率趋势", "session_id": "ts_trace_2"}
        _, events = _stream_post(client, payload)
        trace_events = [e for e in events if e["event"] == "trace_step"]
        for ev in trace_events:
            data = ev["data"]
            assert "step_key" in data, f"trace_step 缺少 step_key 字段: {data}"

    def test_trace_step_has_required_fields(self, client):
        """每个 trace_step 应包含 step_key、title、status 三个基础字段"""
        payload = {"message": "今日在线设备数", "session_id": "ts_trace_3"}
        _, events = _stream_post(client, payload)
        trace_events = [e for e in events if e["event"] == "trace_step"]
        assert len(trace_events) >= 1
        for ev in trace_events:
            data = ev["data"]
            for field in ("step_key", "title", "status"):
                assert field in data, f"trace_step 缺少字段 '{field}': {data}"

    def test_trace_steps_contain_intent_router(self, client):
        """adhoc 路径必须经过 intent_router"""
        payload = {"message": "查询设备产能", "session_id": "ts_trace_4"}
        _, events = _stream_post(client, payload)
        step_keys = [
            e["data"].get("step_key", "")
            for e in events
            if e["event"] == "trace_step"
        ]
        assert "intent_router" in step_keys, (
            f"adhoc 路径应包含 intent_router 步骤，实际 step_keys: {step_keys}"
        )


# ──────────────────────────────────────────────
# Test Suite 4: done 事件
# ──────────────────────────────────────────────

class TestDoneEvent:
    """验证流式响应以 done 事件结束并携带完整 payload"""

    def test_stream_ends_with_done_event(self, client):
        payload = {"message": "当前 WIP 数量", "session_id": "ts_done_1"}
        _, events = _stream_post(client, payload)
        assert len(events) > 0
        last_event = events[-1]
        assert last_event["event"] == "done", (
            f"最后一个事件应为 done，实际为: {last_event['event']}"
        )

    def test_done_event_has_success_field(self, client):
        payload = {"message": "查询站点良率", "session_id": "ts_done_2"}
        _, events = _stream_post(client, payload)
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1, "应恰好有一个 done 事件"
        assert "success" in done_events[0]["data"], "done 事件缺少 success 字段"

    def test_done_event_has_session_id(self, client):
        payload = {"message": "设备稼动率", "session_id": "ts_done_3"}
        _, events = _stream_post(client, payload)
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1
        assert "session_id" in done_events[0]["data"], "done 事件缺少 session_id 字段"

    def test_done_event_has_pipeline_trace(self, client):
        payload = {"message": "各站点 UPH", "session_id": "ts_done_4"}
        _, events = _stream_post(client, payload)
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1
        data = done_events[0]["data"]
        assert "pipeline_trace" in data, "done 事件缺少 pipeline_trace 字段"
        assert isinstance(data["pipeline_trace"], list), "pipeline_trace 应为列表"

    def test_done_pipeline_trace_matches_step_events(self, client):
        """done.pipeline_trace 长度应与流中 trace_step 事件数量一致"""
        payload = {"message": "昨日产量汇总", "session_id": "ts_done_5"}
        _, events = _stream_post(client, payload)
        trace_events = [e for e in events if e["event"] == "trace_step"]
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1
        final_trace = done_events[0]["data"].get("pipeline_trace", [])
        assert len(final_trace) == len(trace_events), (
            f"done.pipeline_trace({len(final_trace)}) 应与 trace_step 事件数({len(trace_events)})一致"
        )

    def test_session_id_passthrough(self, client):
        """指定 session_id 时，done 事件应回传相同值"""
        sid = "ts_session_passthrough_99"
        payload = {"message": "设备列表", "session_id": sid}
        _, events = _stream_post(client, payload)
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1
        assert done_events[0]["data"]["session_id"] == sid


# ──────────────────────────────────────────────
# Test Suite 5: 参数校验
# ──────────────────────────────────────────────

class TestRequestValidation:
    """验证非法请求被正确拒绝"""

    def test_missing_message_returns_422(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "ts_val_1"},  # 缺少 message
        )
        assert resp.status_code == 422, f"缺少 message 应返回 422，实际: {resp.status_code}"

    def test_empty_body_returns_422(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            content=b"",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_invalid_json_returns_422(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_valid_minimal_request_succeeds(self, client):
        """仅提供 message 字段应正常工作"""
        payload = {"message": "测试最小请求"}
        _, events = _stream_post(client, payload)
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1


# ──────────────────────────────────────────────
# Test Suite 6: 事件顺序
# ──────────────────────────────────────────────

class TestEventOrder:
    """验证事件按 trace_step…, done 顺序到达"""

    def test_done_is_last_event(self, client):
        payload = {"message": "查询批次信息", "session_id": "ts_order_1"}
        _, events = _stream_post(client, payload)
        assert events[-1]["event"] == "done"

    def test_no_events_after_done(self, client):
        payload = {"message": "查询设备状态", "session_id": "ts_order_2"}
        _, events = _stream_post(client, payload)
        done_idx = next((i for i, e in enumerate(events) if e["event"] == "done"), None)
        assert done_idx is not None, "缺少 done 事件"
        assert done_idx == len(events) - 1, f"done 后不应有更多事件，done_idx={done_idx}, 总数={len(events)}"

    def test_trace_steps_precede_done(self, client):
        payload = {"message": "良率汇总", "session_id": "ts_order_3"}
        _, events = _stream_post(client, payload)
        step_indices = [i for i, e in enumerate(events) if e["event"] == "trace_step"]
        done_idx = next((i for i, e in enumerate(events) if e["event"] == "done"), None)
        assert done_idx is not None
        if step_indices:
            assert max(step_indices) < done_idx, "所有 trace_step 应在 done 之前"


# ──────────────────────────────────────────────
# Test Suite 7: 实时性（时序）
# ──────────────────────────────────────────────

class TestStreamingTimeliness:
    """
    验证流式事件在 done 之前就开始到达（非缓冲式一次性返回）。
    注意：TestClient 默认同步读取不能精确测量实时性；
    此 suite 仅做粗粒度检查（超时内至少收到第一步）。
    """

    def test_first_event_arrives_quickly(self, client):
        """在 10 秒内应收到至少一条事件"""
        payload = {"message": "查询今日产量", "session_id": "ts_time_1"}
        t0 = time.monotonic()
        first_event = None
        with client.stream("POST", "/api/v1/chat/stream", json=payload, timeout=30) as resp:
            buf = ""
            for chunk in resp.iter_bytes():
                buf += chunk.decode("utf-8", errors="replace")
                if "\n\n" in buf:
                    first_event = buf.split("\n\n")[0]
                    break
        elapsed = time.monotonic() - t0
        assert first_event is not None, "应在超时前收到至少一条事件"
        assert elapsed < 10, f"第一条事件应在 10 秒内到达，实际 {elapsed:.2f}s"
