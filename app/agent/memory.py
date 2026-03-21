"""
Conversation Memory — 对话记忆管理 (Phase C)

实现两层记忆机制:
  1. 短期记忆 (Short-term): 当前会话的最近 N 轮对话，存于内存
  2. 长期记忆 (Long-term): 持久化到 Supabase，支持跨会话检索

核心能力:
  - 自动管理对话窗口 (sliding window)
  - 从历史对话提取上下文摘要
  - 指代消解辅助 (识别"它""上个月""那个表"等)
  - 持久化会话到数据库 (Supabase REST / PG)
"""

import logging
import time
import uuid
from collections import OrderedDict
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ── 配置常量 ──
MAX_SHORT_TERM_TURNS = 10       # 短期记忆保留最近 N 轮 (user+assistant 为 1 轮)
MAX_CONTEXT_MESSAGES = 6        # 注入到 LLM prompt 的最近消息数
MAX_SESSIONS_CACHE = 200        # 内存中最多缓存的会话数
SESSION_TTL_SECONDS = 3600      # 内存中会话过期时间 (1 小时)


class ConversationTurn:
    """一轮对话 (用户问 + 系统答)"""

    def __init__(
        self,
        user_message: str,
        assistant_message: str = "",
        sql: str = "",
        query_result_summary: str = "",
        intent: str = "",
        timestamp: float = None,
    ):
        self.user_message = user_message
        self.assistant_message = assistant_message
        self.sql = sql
        self.query_result_summary = query_result_summary
        self.intent = intent
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_message": self.user_message,
            "assistant_message": self.assistant_message,
            "sql": self.sql,
            "query_result_summary": self.query_result_summary,
            "intent": self.intent,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ConversationTurn":
        return cls(
            user_message=d.get("user_message", ""),
            assistant_message=d.get("assistant_message", ""),
            sql=d.get("sql", ""),
            query_result_summary=d.get("query_result_summary", ""),
            intent=d.get("intent", ""),
            timestamp=d.get("timestamp", time.time()),
        )


class SessionMemory:
    """单个会话的记忆"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.turns: List[ConversationTurn] = []
        self.created_at = time.time()
        self.last_active = time.time()
        self.metadata: Dict[str, Any] = {}  # 会话级元数据

    def add_turn(self, turn: ConversationTurn):
        """添加一轮对话，超出限制时淘汰最早的"""
        self.turns.append(turn)
        self.last_active = time.time()
        if len(self.turns) > MAX_SHORT_TERM_TURNS:
            self.turns = self.turns[-MAX_SHORT_TERM_TURNS:]

    def get_recent_messages(self, n: int = MAX_CONTEXT_MESSAGES) -> List[Dict[str, str]]:
        """获取最近 n 条消息，格式: [{"role": "user/assistant", "content": "..."}]"""
        messages = []
        for turn in self.turns[-(n // 2 + 1):]:
            if turn.user_message:
                messages.append({"role": "user", "content": turn.user_message})
            if turn.assistant_message:
                messages.append({"role": "assistant", "content": turn.assistant_message})
        return messages[-n:]

    def get_context_summary(self) -> str:
        """
        生成当前会话的上下文摘要，用于注入到 LLM prompt。
        包含: 最近的表名/SQL/查询意图，便于指代消解。
        """
        if not self.turns:
            return ""

        parts = []
        # 最近 3 轮的关键信息
        for turn in self.turns[-3:]:
            entry = f"- 用户: {turn.user_message}"
            if turn.sql:
                entry += f"\n  SQL: {turn.sql}"
            if turn.query_result_summary:
                entry += f"\n  结果: {turn.query_result_summary}"
            parts.append(entry)

        return "=== 对话上下文 ===\n" + "\n".join(parts) + "\n=== 上下文结束 ==="

    def get_last_query_context(self) -> Dict[str, Any]:
        """获取上一轮查询的关键信息，用于指代消解"""
        for turn in reversed(self.turns):
            if turn.intent == "query" and turn.sql:
                return {
                    "last_question": turn.user_message,
                    "last_sql": turn.sql,
                    "last_result_summary": turn.query_result_summary,
                    "last_intent": turn.intent,
                }
        return {}

    def is_followup_query(self, current_input: str) -> bool:
        """
        判断当前输入是否是追问/指代查询。
        检测: "那/那个/再/也/上面/换成/改为/它的" 等模式。
        """
        if not self.turns:
            return False

        followup_patterns = [
            # 指代词
            '那', '那个', '那些', '这个', '这些',
            '它的', '它们', '其中',
            # 承接/追加
            '再', '也', '还', '又',
            '再查', '再统计', '再看', '再算',
            '也查', '也统计', '也看', '也算',
            '还有', '另外', '同样', '帮我',
            # 修改/替换
            '换成', '改为', '改成', '换个', '改下',
            '不要', '去掉', '加上', '加个',
            # 时间引用
            '上面', '上个', '下个', '上一个',
            '刚才', '之前', '前面',
            # 疑问承接
            '怎么样', '多少', '呢', '吗', '如何',
            # 对比/扩展
            '对比', '比较', '按', '分别',
            # 字段/列筛选（追问列显示）
            '只需要', '只显示', '只展示', '只保留',
            '显示字段', '展示字段', '显示列', '展示列',
            '这几个字段', '这些字段', '这几列', '这些列',
            '字段就够了', '列就够了',
        ]
        input_lower = current_input.strip()

        # 短查询 + 包含指代词 → 大概率是追问
        if len(input_lower) < 30:
            for p in followup_patterns:
                if p in input_lower:
                    return True

        # "那XXX呢" / "XXX呢" 模式
        if input_lower.endswith('呢') or input_lower.endswith('吗'):
            if any(p in input_lower for p in ['那', '这', '上', '它', '再', '也']):
                return True

        # "再统计下XXX的" 模式
        if input_lower.startswith('再') or input_lower.startswith('也'):
            return True

        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "turns": [t.to_dict() for t in self.turns],
            "created_at": self.created_at,
            "last_active": self.last_active,
            "metadata": self.metadata,
        }


class ConversationMemory:
    """
    全局对话记忆管理器 (单例)

    职责:
    1. 管理内存中的短期会话 (LRU 淘汰)
    2. 持久化到 Supabase (长期记忆)
    3. 提供上下文注入接口供各 Node 使用
    """

    def __init__(self):
        self._sessions: OrderedDict[str, SessionMemory] = OrderedDict()
        self._supabase_client = None
        self._db_available: Optional[bool] = None

    # ------------------------------------------------------------------
    # 会话管理
    # ------------------------------------------------------------------

    def get_or_create_session(self, session_id: Optional[str] = None) -> SessionMemory:
        """获取现有会话或创建新会话"""
        if not session_id:
            session_id = str(uuid.uuid4())

        if session_id in self._sessions:
            session = self._sessions[session_id]
            # LRU: 移到末尾
            self._sessions.move_to_end(session_id)
            return session

        # 尝试从数据库加载
        session = self._load_from_db(session_id)
        if session is None:
            session = SessionMemory(session_id)

        self._sessions[session_id] = session

        # LRU 淘汰
        while len(self._sessions) > MAX_SESSIONS_CACHE:
            evicted_id, evicted = self._sessions.popitem(last=False)
            self._save_to_db(evicted)  # 淘汰前持久化
            logger.debug(f"[memory] Evicted session {evicted_id}")

        return session

    def save_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str = "",
        sql: str = "",
        query_result_summary: str = "",
        intent: str = "",
    ):
        """保存一轮对话"""
        session = self.get_or_create_session(session_id)
        turn = ConversationTurn(
            user_message=user_message,
            assistant_message=assistant_message,
            sql=sql,
            query_result_summary=query_result_summary,
            intent=intent,
        )
        session.add_turn(turn)

        # 异步持久化 (简化版: 每轮都写)
        self._save_to_db(session)

    def get_context_for_llm(
        self, session_id: str, current_input: str
    ) -> Dict[str, Any]:
        """
        为 LLM 准备对话上下文。

        返回:
        {
            "is_followup": bool,           # 是否为追问
            "context_summary": str,        # 注入到 prompt 的上下文摘要
            "recent_messages": [...],      # 最近的对话消息列表
            "last_query_context": {...},   # 上一轮查询的关键信息
            "resolved_input": str,         # 指代消解后的输入 (或原始输入)
        }
        """
        session = self.get_or_create_session(session_id)

        is_followup = session.is_followup_query(current_input)
        context_summary = session.get_context_summary()
        recent_messages = session.get_recent_messages()
        last_ctx = session.get_last_query_context()

        # 指代消解: 如果是追问，将上下文信息合并到输入中
        resolved_input = current_input
        if is_followup and last_ctx:
            resolved_input = self._resolve_reference(
                current_input, last_ctx
            )

        return {
            "is_followup": is_followup,
            "context_summary": context_summary,
            "recent_messages": recent_messages,
            "last_query_context": last_ctx,
            "resolved_input": resolved_input,
        }

    def _resolve_reference(self, current_input: str, last_ctx: Dict) -> str:
        """
        指代消解 — 使用 LLM 将追问中的隐含引用补全为完整独立的查询。

        例:
          上一轮: "统计颗粒检测站点的在制品数量" → SQL: SELECT COUNT(*)...
          当前: "再统计下包装站点的" → 消解后: "统计包装站点的在制品数量"
          当前: "那上个月呢" → 消解后: "统计颗粒检测站点上个月的在制品数量"
          当前: "换成 wafers 表" → 消解后: "查询 wafers 表的数量"
        """
        last_q = last_ctx.get("last_question", "")
        last_sql = last_ctx.get("last_sql", "")
        last_result = last_ctx.get("last_result_summary", "")

        if not last_q:
            return current_input

        logger.info(
            f"[memory] Resolving reference: '{current_input}' "
            f"(followup to: '{last_q[:50]}...')"
        )

        # ── 尝试用 LLM 做指代消解，生成完整独立的查询 ──
        try:
            from app.agent.llm import get_agent_llm
            llm = get_agent_llm()

            prompt = (
                f"你是 MES 系统的查询助手，用户正在进行多轮对话查询。\n\n"
                f"上一轮用户的问题: {last_q}\n"
                f"上一轮生成的 SQL: {last_sql}\n"
            )
            if last_result:
                prompt += f"上一轮查询结果摘要: {last_result}\n"
            prompt += (
                f"\n用户当前的追问: {current_input}\n\n"
                f"请将用户的追问改写为一个完整的、独立的自然语言查询，"
                f"使其不依赖上下文也能被正确理解。\n"
                f"要求:\n"
                f"1. 保留上一轮查询的结构和逻辑（如 JOIN、过滤条件、聚合方式等）\n"
                f"2. 只替换用户追问中明确要求修改的部分\n"
                f"3. 只输出改写后的查询语句，不要解释\n"
                f"4. 使用中文自然语言，不要输出 SQL"
            )

            response = llm.invoke(prompt)
            resolved = response.content if hasattr(response, "content") else str(response)
            resolved = resolved.strip().strip('"').strip("'")

            if resolved and len(resolved) > 5:
                logger.info(
                    f"[memory] LLM resolved: '{current_input}' → '{resolved}'"
                )
                return resolved

        except Exception as e:
            logger.warning(f"[memory] LLM reference resolution failed: {e}")

        # ── Fallback: 构建拼接的上下文提示 ──
        resolved = (
            f"[上一个问题: {last_q}]\n"
            f"[上一个SQL: {last_sql}]\n"
            f"[当前追问: {current_input}]\n"
            f"请理解追问意图，相当于用户想要: "
        )

        logger.info(
            f"[memory] Fallback resolution: '{current_input}'"
        )

        return resolved

    # ------------------------------------------------------------------
    # 数据库持久化 (Supabase REST)
    # ------------------------------------------------------------------

    def _get_supabase(self):
        """获取 Supabase 客户端"""
        if self._supabase_client is None:
            try:
                from app.services.supabase_client import get_supabase_client
                sc = get_supabase_client()
                if sc and sc.client:
                    self._supabase_client = sc.client
                else:
                    self._db_available = False
                    return None
            except Exception:
                self._db_available = False
                return None
        return self._supabase_client

    def _save_to_db(self, session: SessionMemory):
        """持久化会话到 Supabase (使用现有 chat_sessions + chat_messages 表)"""
        if self._db_available is False:
            return
        try:
            client = self._get_supabase()
            if not client:
                return

            import json
            from datetime import datetime

            # 1. Upsert chat_sessions
            session_data = {
                "id": session.session_id,
                "name": session.turns[0].user_message[:50] if session.turns else "新对话",
                "created_at": datetime.fromtimestamp(session.created_at).isoformat(),
            }
            client.table("chat_sessions").upsert(
                session_data, on_conflict="id"
            ).execute()

            # 2. Upsert latest turn as chat_messages
            if session.turns:
                latest = session.turns[-1]
                ts = datetime.fromtimestamp(latest.timestamp).isoformat()
                # Save user message
                user_msg_id = f"{session.session_id}-u-{len(session.turns)}"
                client.table("chat_messages").upsert({
                    "id": user_msg_id,
                    "session_id": session.session_id,
                    "type": "user",
                    "content": latest.user_message,
                    "timestamp": ts,
                    "created_at": ts,
                    "intent_data": json.dumps({"intent": latest.intent}, ensure_ascii=False) if latest.intent else None,
                }, on_conflict="id").execute()

                # Save assistant message
                if latest.assistant_message:
                    asst_msg_id = f"{session.session_id}-a-{len(session.turns)}"
                    result_data = None
                    if latest.sql or latest.query_result_summary:
                        result_data = json.dumps({
                            "sql": latest.sql,
                            "summary": latest.query_result_summary,
                        }, ensure_ascii=False)
                    client.table("chat_messages").upsert({
                        "id": asst_msg_id,
                        "session_id": session.session_id,
                        "type": "assistant",
                        "content": latest.assistant_message,
                        "timestamp": ts,
                        "created_at": ts,
                        "result_data": result_data,
                    }, on_conflict="id").execute()

            self._db_available = True
            logger.debug(f"[memory] Saved session {session.session_id} to DB")
        except Exception as e:
            logger.warning(f"[memory] DB save failed: {e}")
            # 不阻断: 内存中仍然可用

    def _load_from_db(self, session_id: str) -> Optional[SessionMemory]:
        """从 Supabase 加载会话 (使用现有 chat_messages 表)"""
        if self._db_available is False:
            return None
        try:
            client = self._get_supabase()
            if not client:
                return None

            import json

            # 检查 session 是否存在
            sess_resp = client.table("chat_sessions").select("id,created_at").eq(
                "id", session_id
            ).execute()
            if not sess_resp.data:
                return None

            # 加载消息
            msg_resp = client.table("chat_messages").select(
                "type,content,timestamp,intent_data,result_data"
            ).eq("session_id", session_id).order("timestamp").execute()

            if not msg_resp.data:
                return None

            session = SessionMemory(session_id)
            # 将消息配对为 turns
            messages = msg_resp.data or []
            i = 0
            while i < len(messages):
                msg = messages[i]
                if msg["type"] == "user":
                    user_msg = msg["content"]
                    assistant_msg = ""
                    sql = ""
                    summary = ""
                    intent = ""

                    # 解析 intent_data
                    if msg.get("intent_data"):
                        try:
                            idata = msg["intent_data"] if isinstance(msg["intent_data"], dict) else json.loads(msg["intent_data"])
                            intent = idata.get("intent", "")
                        except (json.JSONDecodeError, TypeError):
                            pass

                    # 查看下一条是否为 assistant
                    if i + 1 < len(messages) and messages[i + 1]["type"] == "assistant":
                        asst = messages[i + 1]
                        assistant_msg = asst["content"]
                        if asst.get("result_data"):
                            try:
                                rdata = asst["result_data"] if isinstance(asst["result_data"], dict) else json.loads(asst["result_data"])
                                sql = rdata.get("sql", "")
                                summary = rdata.get("summary", "")
                            except (json.JSONDecodeError, TypeError):
                                pass
                        i += 1

                    session.add_turn(ConversationTurn(
                        user_message=user_msg,
                        assistant_message=assistant_msg,
                        sql=sql,
                        query_result_summary=summary,
                        intent=intent,
                    ))
                i += 1

            self._db_available = True
            logger.info(
                f"[memory] Loaded session {session_id} from DB "
                f"({len(session.turns)} turns)"
            )
            return session
        except Exception as e:
            logger.warning(f"[memory] DB load failed: {e}")
            return None

    # ------------------------------------------------------------------
    # 会话历史查询 API
    # ------------------------------------------------------------------

    def get_session_history(
        self, session_id: str
    ) -> List[Dict[str, Any]]:
        """获取完整的会话历史"""
        session = self.get_or_create_session(session_id)
        return [t.to_dict() for t in session.turns]

    def get_latest_session(self) -> Optional[Dict[str, Any]]:
        """
        返回最近活跃的一条会话信息（前端打开页面时复用，避免每次新建）。
        优先从内存中取；内存为空时查 Supabase。
        若完全没有历史会话则返回 None。
        """
        # 1. 从内存中取最近活跃的（OrderedDict 末尾为最新）
        for sid, s in reversed(self._sessions.items()):
            if s.turns:  # 只返回有真实对话的 session
                return {
                    "session_id": sid,
                    "name": s.turns[0].user_message[:50],
                    "turn_count": len(s.turns),
                    "last_active": datetime.fromtimestamp(s.last_active).isoformat(),
                    "created_at": datetime.fromtimestamp(s.created_at).isoformat(),
                    "last_message": s.turns[-1].user_message,
                }

        # 2. 内存中没有，查 DB
        try:
            client = self._get_supabase()
            if client:
                resp = client.table("chat_sessions").select(
                    "id,name,created_at"
                ).order("created_at", desc=True).limit(1).execute()
                if resp.data:
                    row = resp.data[0]
                    return {
                        "session_id": row["id"],
                        "name": row.get("name", ""),
                        "created_at": row.get("created_at", ""),
                    }
        except Exception as e:
            logger.warning(f"[memory] get_latest_session DB query failed: {e}")

        return None

    def list_recent_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """列出最近活跃的会话"""
        # 从内存中获取
        sessions = []
        for sid, s in reversed(self._sessions.items()):
            sessions.append({
                "session_id": sid,
                "turn_count": len(s.turns),
                "last_active": datetime.fromtimestamp(s.last_active).isoformat(),
                "created_at": datetime.fromtimestamp(s.created_at).isoformat(),
                "last_message": s.turns[-1].user_message if s.turns else "",
            })
            if len(sessions) >= limit:
                break

        # 如果内存中不够，尝试从 DB 补充
        if len(sessions) < limit:
            try:
                client = self._get_supabase()
                if client:
                    resp = client.table("chat_sessions").select(
                        "id,name,created_at"
                    ).order(
                        "created_at", desc=True
                    ).limit(limit).execute()
                    existing_ids = {s["session_id"] for s in sessions}
                    for row in (resp.data or []):
                        if row["id"] not in existing_ids:
                            sessions.append({
                                "session_id": row["id"],
                                "name": row.get("name", ""),
                                "created_at": row.get("created_at", ""),
                            })
            except Exception:
                pass

        return sessions[:limit]

    def clear_session(self, session_id: str) -> bool:
        """清除指定会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]

        try:
            client = self._get_supabase()
            if client:
                # 先删除消息，再删除会话
                client.table("chat_messages").delete().eq(
                    "session_id", session_id
                ).execute()
                client.table("chat_sessions").delete().eq(
                    "id", session_id
                ).execute()
        except Exception as e:
            logger.warning(f"[memory] Failed to delete session from DB: {e}")

        return True


# ── 全局单例 ──
conversation_memory = ConversationMemory()
