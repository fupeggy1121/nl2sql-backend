"""Phase C 单元测试"""
import sys
sys.path.insert(0, '.')

# Test 1: Import memory module
from app.agent.memory import conversation_memory, ConversationTurn, SessionMemory
print('✅ memory module imported')

# Test 2: Session creation and turns
s = conversation_memory.get_or_create_session('test-123')
s.add_turn(ConversationTurn(
    user_message='查询 carriers 表的数量',
    assistant_message='查询返回 238 条记录',
    sql='SELECT COUNT(*) FROM carriers',
    intent='query',
))
print(f'✅ Session test-123: {len(s.turns)} turn(s)')

# Test 3: Follow-up detection
assert s.is_followup_query('那上个月呢') == True
assert s.is_followup_query('查询所有设备信息') == False
print('✅ Follow-up detection works')

# Test 4: Context for LLM
ctx = conversation_memory.get_context_for_llm('test-123', '那上个月呢')
assert ctx['is_followup'] == True
assert 'carriers' in ctx['resolved_input']
print(f'✅ Context resolved: is_followup={ctx["is_followup"]}')
print(f'   resolved_input: {ctx["resolved_input"][:80]}...')

# Test 5: Last query context
last = s.get_last_query_context()
assert last['last_sql'] == 'SELECT COUNT(*) FROM carriers'
print(f'✅ Last query context: {last["last_sql"]}')

# Test 6: Context summary
summary = s.get_context_summary()
assert '对话上下文' in summary
assert 'carriers' in summary
print(f'✅ Context summary ({len(summary)} chars)')

# Test 7: Sliding window
for i in range(12):
    s.add_turn(ConversationTurn(user_message=f'query {i}'))
assert len(s.turns) == 10
print(f'✅ Sliding window: {len(s.turns)} turns (max=10)')

# Test 8: Session list
sessions = conversation_memory.list_recent_sessions()
assert len(sessions) > 0
print(f'✅ Recent sessions: {len(sessions)}')

# Test 9: Table extraction helper
from app.agent.nodes.query_planner import _extract_table_from_sql
assert _extract_table_from_sql('SELECT COUNT(*) FROM carriers') == 'carriers'
assert _extract_table_from_sql('SELECT * FROM wafers WHERE id > 5') == 'wafers'
assert _extract_table_from_sql('WITH cte AS (SELECT 1) SELECT * FROM cte') == 'cte'
print('✅ Table extraction from SQL works')

# Test 10: Graph compilation
from app.agent.graph import build_agent_graph, compile_agent
graph = build_agent_graph()
print('✅ Graph built')
app = compile_agent()
nodes = list(app.get_graph().nodes.keys())
print(f'✅ Agent compiled: {len(nodes)} nodes')
print(f'   Nodes: {nodes}')

# Verify memory nodes exist
assert 'memory_loader' in nodes
assert 'memory_saver' in nodes
print('✅ Memory nodes registered in graph')

# Test 11: Clear session
conversation_memory.clear_session('test-123')
assert 'test-123' not in conversation_memory._sessions
print('✅ Session cleared')

# Test 12: Serialization
s2 = conversation_memory.get_or_create_session('test-456')
s2.add_turn(ConversationTurn(
    user_message='test message',
    assistant_message='test response',
    sql='SELECT 1',
))
d = s2.to_dict()
assert d['session_id'] == 'test-456'
assert len(d['turns']) == 1
print('✅ Session serialization works')

# Test 13: ConversationTurn from_dict
t = ConversationTurn.from_dict(d['turns'][0])
assert t.user_message == 'test message'
assert t.sql == 'SELECT 1'
print('✅ Turn deserialization works')

print('\n🎉 All 13 Phase C unit tests passed!')
