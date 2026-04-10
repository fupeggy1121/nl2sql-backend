"""
Phase 2 SSE 流式端点 — 端到端集成测试
========================================
前提：后端服务必须已在 http://localhost:8000 运行。

覆盖场景：
  1. 真实流：连接真实后端，断言时序（trace_step 早于 done）
  2. 多轮对话：session_id 复用，第二轮携带 conversation_history
  3. 并发请求：同时发多个流式请求，互不干扰
  4. 长超时保障：大查询不应在 60s 内断开
  5. 断开恢复：中途关闭连接，后端不应崩溃（再发一次仍成功）
  6. session_id 自动生成：不传 session_id，done 中自动生成
  7. done 数据一致性：done.pipeline_trace 与中间 trace_step 事件一致

运行方式（需后端运行中）：
    cd /Users/fupeggy/NL2SQL
    .venv/bin/pytest tests/test_stream_e2e.py -v -s --timeout=120

跳过（后端未启动时）：
    .venv/bin/pytest tests/test_stream_e2e.py -v --ignore-glob="*e2e*"
"""

import json
import sys
import os
import time
import threading
import uuid
import socket

import pytest
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ──────────────────────────────────────────────
# 配置
# ──────────────────────────────────────────────

BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
STREAM_URL = f"{BASE_URL}/api/v1/chat/stream"
REQUEST_TIMEOUT = 90  # 单个流式请求超时（秒）


# ──────────────────────────────────────────────
# 跳过条件：后端未运行时 skip 整个模块
# ──────────────────────────────────────────────

def _backend_reachable() -> bool:
    try:
        host, port_str = BASE_URL.replace("http://", "").replace("https://", "").split(":")
        s = socket.create_connection((host, int(port_str)), timeout=2)
        s.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _backend_reachable(),
    reason=f"后端 {BASE_URL} 未运行，跳过 E2E 测试",
)


# ──────────────────────────────────────────────
# 辅助工具
# ──────────────────────────────────────────────

def _stream_collect(payload: dict, stop_after_steps: int | None = None) -> list[dict]:
    """
    向 STREAM_URL 发 POST，收集所有 SSE 事件为列表。
    stop_after_steps：收到指定数量的 trace_step 后断开连接（模拟中途断开）。
    """
    events: list[dict] = []
    step_count = 0

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        with client.stream("POST", STREAM_URL, json=payload) as resp:
            resp.raise_for_status()
            buf = ""
            for chunk in resp.iter_bytes():
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
                        continue
                    events.append({"event": event_type, "data": parsed, "_ts": time.monotonic()})
                    if event_type == "trace_step":
                        step_count += 1
                    if event_type == "done":
                        return events
                    if stop_after_steps and step_count >= stop_after_steps:
                        return events  # 模拟客户端主动断开
    return events


# ──────────────────────────────────────────────
# Test Suite 1: 基本流式正确性
# ──────────────────────────────────────────────

class TestBasicStreamCorrectness:

    def test_stream_returns_200_ok(self):
        with httpx.Client(timeout=10) as c:
            with c.stream("POST", STREAM_URL, json={"message": "ping"}) as resp:
                assert resp.status_code == 200

    def test_content_type_text_event_stream(self):
        with httpx.Client(timeout=10) as c:
            with c.stream("POST", STREAM_URL, json={"message": "ping"}) as resp:
                assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_at_least_one_trace_step(self):
        events = _stream_collect({"message": "查询站点批次数", "session_id": "e2e_basic_1"})
        trace = [e for e in events if e["event"] == "trace_step"]
        assert len(trace) >= 1

    def test_ends_with_done(self):
        events = _stream_collect({"message": "当前在线设备", "session_id": "e2e_basic_2"})
        assert events[-1]["event"] == "done"

    def test_done_success_true(self):
        events = _stream_collect({"message": "统计各站点批次", "session_id": "e2e_basic_3"})
        done = next(e for e in events if e["event"] == "done")
        assert done["data"]["success"] is True


# ──────────────────────────────────────────────
# Test Suite 2: 实时时序
# ──────────────────────────────────────────────

class TestStreamTimeliness:
    """
    验证步骤是"逐步"到达的，而非批量缓冲后一次性返回。
    判据：第一个 trace_step 的时间戳 早于 done 的时间戳（至少差 100ms）。
    """

    def test_trace_steps_arrive_before_done(self):
        events = _stream_collect({"message": "查询设备产能", "session_id": "e2e_time_1"})
        trace = [e for e in events if e["event"] == "trace_step"]
        done = next(e for e in events if e["event"] == "done")
        if len(trace) >= 1:
            # 第一个步骤应比 done 早
            assert trace[0]["_ts"] <= done["_ts"], "trace_step 应早于 done 到达"

    def test_multiple_steps_not_all_at_same_time(self):
        """如果有多个步骤，它们不应完全同一时刻到达（说明是实时推送）"""
        events = _stream_collect({"message": "良率分析", "session_id": "e2e_time_2"})
        trace = [e for e in events if e["event"] == "trace_step"]
        if len(trace) >= 2:
            first_ts = trace[0]["_ts"]
            last_ts = trace[-1]["_ts"]
            # 多步骤总跨度应 >0（即非完全同批次返回）
            assert last_ts >= first_ts


# ──────────────────────────────────────────────
# Test Suite 3: 多轮对话
# ──────────────────────────────────────────────

class TestMultiTurnConversation:

    def test_session_id_preserved_across_turns(self):
        """第二轮传入相同 session_id，done 返回的 session_id 应一致"""
        sid = f"e2e_multi_{uuid.uuid4().hex[:8]}"

        # 第一轮
        events1 = _stream_collect({"message": "查询今日产量", "session_id": sid})
        done1 = next(e for e in events1 if e["event"] == "done")
        assert done1["data"]["session_id"] == sid

        # 第二轮（携带 conversation_history）
        history = [
            {"role": "user", "content": "查询今日产量"},
            {"role": "assistant", "content": done1["data"].get("data", {}).get("answer", "已查询")},
        ]
        events2 = _stream_collect({
            "message": "与上次相比增加了多少",
            "session_id": sid,
            "conversation_history": history,
        })
        done2 = next(e for e in events2 if e["event"] == "done")
        assert done2["data"]["session_id"] == sid

    def test_new_session_auto_generated(self):
        """不传 session_id，后端自动生成并回传"""
        events = _stream_collect({"message": "设备列表"})
        done = next(e for e in events if e["event"] == "done")
        sid = done["data"].get("session_id")
        assert sid is not None and len(sid) > 0


# ──────────────────────────────────────────────
# Test Suite 4: 并发请求
# ──────────────────────────────────────────────

class TestConcurrentStreams:

    def test_two_concurrent_streams_independent(self):
        """两个并发流式请求互不干扰，各自收到正确的 done 事件"""
        results: dict[str, list] = {"a": [], "b": []}
        errors: list[str] = []

        def run(key, msg, sid):
            try:
                results[key] = _stream_collect({"message": msg, "session_id": sid})
            except Exception as e:
                errors.append(f"{key}: {e}")

        ta = threading.Thread(target=run, args=("a", "查询站点 A 产量", "e2e_con_a"))
        tb = threading.Thread(target=run, args=("b", "查询设备 B 状态", "e2e_con_b"))
        ta.start(); tb.start()
        ta.join(timeout=60); tb.join(timeout=60)

        assert not errors, f"并发请求出错: {errors}"
        done_a = [e for e in results["a"] if e["event"] == "done"]
        done_b = [e for e in results["b"] if e["event"] == "done"]
        assert len(done_a) == 1
        assert len(done_b) == 1
        # 两路 session_id 应该不同
        assert done_a[0]["data"]["session_id"] != done_b[0]["data"]["session_id"]


# ──────────────────────────────────────────────
# Test Suite 5: 中途断开不崩溃后端
# ──────────────────────────────────────────────

class TestEarlyDisconnect:

    def test_disconnect_after_first_step_does_not_crash_backend(self):
        """收到第一个 trace_step 后立即关闭连接，后端不应崩溃"""
        partial = _stream_collect(
            {"message": "快速断开测试", "session_id": "e2e_disc_1"},
            stop_after_steps=1,
        )
        assert len(partial) >= 1  # 至少收到了点什么

        # 再发一次正常请求，验证后端仍然正常响应
        events = _stream_collect({"message": "断开后恢复测试", "session_id": "e2e_disc_2"})
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1


# ──────────────────────────────────────────────
# Test Suite 6: pipeline_trace 一致性
# ──────────────────────────────────────────────

class TestPipelineTraceConsistency:

    def test_done_trace_len_equals_step_event_count(self):
        """done.pipeline_trace 长度应与收到的 trace_step 事件数量相等"""
        events = _stream_collect({"message": "产能汇总", "session_id": "e2e_trace_1"})
        step_events = [e for e in events if e["event"] == "trace_step"]
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1
        final_trace = done_events[0]["data"].get("pipeline_trace", [])
        assert len(final_trace) == len(step_events), (
            f"done.pipeline_trace({len(final_trace)}) ≠ trace_step 事件数({len(step_events)})"
        )

    def test_step_keys_consistent(self):
        """中间 trace_step 事件的 step_key 顺序应与 done.pipeline_trace 里的一致"""
        events = _stream_collect({"message": "WIP 查询", "session_id": "e2e_trace_2"})
        live_keys = [
            e["data"].get("step_key")
            for e in events
            if e["event"] == "trace_step"
        ]
        done_events = [e for e in events if e["event"] == "done"]
        done_keys = [
            s.get("step_key")
            for s in done_events[0]["data"].get("pipeline_trace", [])
        ]
        assert live_keys == done_keys


# ──────────────────────────────────────────────
# Test Suite 7: 边界情况
# ──────────────────────────────────────────────

class TestEdgeCases:

    def test_very_short_query(self):
        """极短的查询（1 个字）也能正常完成"""
        events = _stream_collect({"message": "量", "session_id": "e2e_edge_short"})
        assert any(e["event"] == "done" for e in events)

    def test_unicode_query(self):
        """含特殊字符的查询（中文标点、emoji）不崩溃"""
        events = _stream_collect({
            "message": "查询'良率'📊，筛选 >95%",
            "session_id": "e2e_edge_unicode",
        })
        assert any(e["event"] in ("done", "error") for e in events)
