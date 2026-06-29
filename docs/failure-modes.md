# Agent Failure Mode Catalog

The 8 most common fatal scenarios when building AI agents, and how agent-fender defends against each.

---

## 1. "Why is it spinning forever?" — No Timeout Hang

**Without guardrails**: `ollama.chat()` and `execute_tool()` have no timeout. Requests hang indefinitely when stuck, leaking coroutines.

```python
# Before: bare calls
response = ollama.chat(model="qwen", messages=[...])
result = execute_tool("delete_file", {...})
```

**With agent-fender**:

```python
# After: safe_llm + safe_tool
result = await fender.safe_llm(ollama.chat, model="qwen", messages=[...])
if not result.success:
    return {"final_reply": result.user_message}

tr = await fender.safe_tool(execute_tool, "delete_file", {...})
if not tr.success:
    tool_failures += 1
```

**Defense**: `asyncio.wait_for` timeout control. LLM defaults to 60s, tools to 30s. Returns structured errors instead of raising exceptions on timeout.

---

## 2. "Why is my bill so high?" — Infinite Loops

**Without guardrails**: LLM repeatedly selects tools without stopping. Hundreds of LLM calls burned in a single conversation.

```python
# Before: no loop limit
async def action_node(state):
    response = ollama.chat(messages=..., tools=...)  # LLM may keep picking tools
    tool_names = [tc["function"]["name"] for tc in response["message"]["tool_calls"]]
    ...
```

**With agent-fender**:

```python
# After: preflight circuit breaker
breaker = fender.preflight(loop_count=state.loop_counter, tool_failures=failures)
if breaker.should_break:
    return {"final_reply": breaker.fallback_reply}
# Passed → continue LLM call
```

**Defense**: Circuit breaks when `loop_count >= max_loop_count`. Returns fallback reply. Doesn't burn the LLM, doesn't burn the user.

---

## 3. "Why did a simple request cost $47?" — No Token Budget

**Without guardrails**: The agent works correctly — no loops, no timeouts, no errors. But a single conversation makes 15 LLM calls with large prompts, burning 200k tokens. The developer discovers this when the API bill arrives. Guards 1–6 cover execution safety; none of them cover resource consumption.

```python
# Before: no token tracking
async def action_node(state):
    response = await llm.call(messages=state.messages, tools=[...])
    # Each call uses context window, but no one is counting
```

**With agent-fender**:

```python
# After: token budget in config + preflight
config = FenderConfig(token_budget=100_000)  # 100K token limit
fender = AgentFender(config)

# In the agent loop — accumulate token usage
tokens_used = 0
result = await fender.safe_llm(llm.chat, messages=[...])
if result.success:
    tokens_used += fender.count_tokens(str(result.data))

# Check at preflight before the next LLM call
breaker = fender.preflight(
    loop_count=state.loop_count,
    tool_failures=failures,
    tokens_used=tokens_used,
)
if breaker.should_break:
    return {"final_reply": breaker.fallback_reply}
```

**Defense**: `AgentFender.preflight()` checks cumulative token usage against a configurable limit. The agent stops before the bill does. The default `count_tokens()` uses `len(text)//4` approximation; pass a custom `token_counter` (e.g., tiktoken) via `FenderConfig` for precise counting.

---

## 4. "Why was that file deleted?" — Silent Dangerous Execution

**Without guardrails**: LLM selects `delete_file` and executes it immediately without any human confirmation.

```python
# Before: execute whatever the LLM picks
for tc in response["message"]["tool_calls"]:
    result = execute_tool(tc.name, tc.args)
```

**With agent-fender**:

```python
# After: check_dangerous pre-execution check
tool_names = [tc["function"]["name"] for tc in raw_calls]
approval = fender.check_tools(tool_names)
if approval.requires_approval:
    # Trigger LangGraph interrupt(), wait for human approval
    decision = interrupt(approval.message)
```

**Defense**: `check_dangerous()` intercepts before execution. Dangerous tool list is configurable.

---

## 5. "Why was it deleted when I just said 'yes'?" — Accidental Approval

**Without guardrails**: Keyword matching happens before pending-check. A previous approval is still pending, the user says "yes" in normal conversation, and it's misinterpreted as approving the cancellation.

```python
# Before: match keyword first, check pending later
if msg in ("yes", "approve"):
    return _resume_graph(approved=True)  # ← previous round's approval triggered by mistake
if _has_pending_interrupt(thread_id):
    ...
```

**With agent-fender + main.py fix**:

```python
# After: check pending first, then match keyword
if _has_pending_interrupt(thread_id):
    if msg in ("yes", "approve"):
        return _resume_graph(approved=True)
    return "You have a pending approval"
# No pending interrupt → treat "yes" as normal message
```

**Defense**: `check_dangerous()` provides pure judgment (which tools need approval). The main.py fix ensures keywords are only treated as approval signals when an interrupt is actually pending.

---

## 6. "Why does it keep retrying after failure?" — Tool Cascade Failure

**Without guardrails**: One tool fails, the LLM picks another tool and keeps going. Errors accumulate until unrecoverable.

```python
# Before: no failure counting
for tc in raw_calls:
    result = execute_tool(tc.name, tc.args)
    reply = polish(result)  # continues even after failure
```

**With agent-fender**:

```python
# After: preflight checks tool_failures
breaker = fender.preflight(loop_count=state.loop_counter, tool_failures=tool_failures)
if breaker.should_break:
    return {"final_reply": breaker.fallback_reply}

for tc in raw_calls:
    tr = await fender.safe_tool(execute_tool, tc.name, tc.args)
    if not tr.success:
        tool_failures += 1  # Accumulate; next preflight may trigger tool_failures breaker
```

**Defense**: After 3 consecutive failures (configurable), `preflight()` trips the circuit breaker.

---

## 7. "Why does it forget everything after restart?" — In-Memory Amnesia

**Without guardrails**: `MemorySaver()` stores all state in process memory. `uvicorn --reload` or `docker restart` → everything is lost.

```python
# Before: in-memory storage
graph.compile(checkpointer=MemorySaver())
```

**Fix**:

```python
# After: SqliteSaver for persistence
from langgraph.checkpoint.sqlite import SqliteSaver
graph.compile(checkpointer=SqliteSaver.from_conn_string("checkpoints.db"))
```

**Note**: This is a LangGraph-level fix, not part of the agent-fender library itself. It's included in `failure-modes.md` because it's one of the most common pitfalls in real-world development.

---

## 8. "Why does it work sometimes but not others?" — Errors Silently Swallowed

**Without guardrails**: Bare `try/except` returns only "Service unavailable" without distinguishing timeout/connection/format errors. Debugging means guessing from logs.

```python
# Before: errors swallowed
try:
    response = ollama.chat(...)
except Exception:
    reply = "Service unavailable"  # Timeout? Connection error? Unknown
```

**With agent-fender**:

```python
# After: LLMResult.error_type classification
result = await fender.safe_llm(ollama.chat, ...)
if not result.success:
    log.error(f"LLM fail: {result.error_type} - {result.error_message}")
    return {"final_reply": result.user_message}
    # error_type: "timeout" | "connection" | "response"
```

**Defense**: `LLMResult.error_type` and `SafeToolResult.error_type` precisely classify error types. Retryable (timeout) vs non-retryable (connection) is immediately clear.
