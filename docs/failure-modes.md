# Agent 失败模式手册

开发 AI Agent 时最常见的 7 种致命场景，以及 agent-fender 如何防御。

---

## 1. "为什么一直转圈？" — 无超时悬挂

**没加护栏**：`ollama.chat()` 和 `execute_tool()` 都没有 timeout，卡住时请求永久挂起，协程泄漏。

```python
# Before: 裸调用
response = ollama.chat(model="qwen", messages=[...])
result = execute_tool("cancel_order", {...})
```

**加 agent-fender**：

```python
# After: safe_llm + safe_tool
result = await guard.safe_llm(ollama.chat, model="qwen", messages=[...])
if not result.success:
    return {"final_reply": result.user_message}

tr = await guard.safe_tool(execute_tool, "cancel_order", {...})
if not tr.success:
    tool_failures += 1
```

**防什么**：`asyncio.wait_for` 超时控制。LLM 默认 60s，工具默认 30s。超时后返回结构化错误而非抛异常。

---

## 2. "为什么账单这么贵？" — 无限循环

**没加护栏**：LLM 反复选工具不停止，一次对话烧几百次 LLM 调用。

```python
# Before: 无循环限制
async def action_node(state):
    response = ollama.chat(messages=..., tools=...)  # LLM 可能一直选工具
    tool_names = [tc["function"]["name"] for tc in response["message"]["tool_calls"]]
    ...
```

**加 agent-fender**：

```python
# After: preflight 熔断
breaker = guard.preflight(loop_count=state.loop_counter, tool_failures=failures)
if breaker.should_break:
    return {"final_reply": breaker.fallback_reply}
# 通过 → 继续 LLM 调用
```

**防什么**：`loop_count >= max_loop_count` 时熔断，直接返回兜底回复。不烧 LLM、不烧用户。

---

## 3. "为什么订单被取消了？" — 静默执行危险操作

**没加护栏**：LLM 选中 `cancel_order`，直接执行，没有任何人工确认。

```python
# Before: LLM 选什么就执行什么
for tc in response["message"]["tool_calls"]:
    result = execute_tool(tc.name, tc.args)
```

**加 agent-fender**：

```python
# After: check_dangerous 前置判断
tool_names = [tc["function"]["name"] for tc in raw_calls]
approval = guard.check_tools(tool_names)
if approval.requires_approval:
    # 触发 LangGraph interrupt()，等人工审批
    decision = interrupt(approval.message)
```

**防什么**：`check_dangerous()` 在工具执行前拦截。危险工具名单可配置。

---

## 4. "为什么我说 yes 它就取消了订单？" — 误批准

**没加护栏**：关键词检测在挂起检查之前。上一轮审批挂着，这轮聊天说了个 yes，被当成"批准取消订单"。

```python
# Before: 先匹配关键词，后检查挂起
if msg in ("yes", "批准"):
    return _resume_graph(approved=True)  # ← 上一轮的审批被误触发了
if _has_pending_interrupt(thread_id):
    ...
```

**加 agent-fender + main.py 修复**：

```python
# After: 先检查挂起，再匹配关键词
if _has_pending_interrupt(thread_id):
    if msg in ("yes", "批准"):
        return _resume_graph(approved=True)
    return "有审批未处理"
# 无挂起 → yes 就当普通消息
```

**防什么**：`check_dangerous()` 提供纯判断（哪些工具需要审批）。main.py 修复确保关键词只在有挂起中断时才作为审批信号。

---

## 5. "为什么失败后还在重试？" — 工具级联失败

**没加护栏**：一个工具失败后，LLM 换另一个工具继续调，错误累积到不可收拾。

```python
# Before: 无失败计数
for tc in raw_calls:
    result = execute_tool(tc.name, tc.args)
    reply = polish(result)  # 失败了也继续
```

**加 agent-fender**：

```python
# After: preflight 检查 tool_failures
breaker = guard.preflight(loop_count=state.loop_counter, tool_failures=tool_failures)
if breaker.should_break:
    return {"final_reply": breaker.fallback_reply}

for tc in raw_calls:
    tr = await guard.safe_tool(execute_tool, tc.name, tc.args)
    if not tr.success:
        tool_failures += 1  # 累加，下次 preflight 可能触发 tool_failures 熔断
```

**防什么**：连续失败满 3 次（可配置），`preflight()` 直接熔断。

---

## 6. "为什么重启后全忘了？" — 内存存储失忆

**没加护栏**：`MemorySaver()` 所有状态在进程内存。`uvicorn --reload` 或 `docker restart` → 全部丢失。

```python
# Before: 内存存储
graph.compile(checkpointer=MemorySaver())
```

**修复**：

```python
# After: SqliteSaver 落盘
from langgraph.checkpoint.sqlite import SqliteSaver
graph.compile(checkpointer=SqliteSaver.from_conn_string("checkpoints.db"))
```

**注**：这是 LangGraph 层面的修复，不属于 agent-fender 库本身。但 `failure-modes.md` 把它作为第 6 个模式记录，因为这是真实开发中最常见的坑之一。

---

## 7. "为什么偶尔好偶尔坏？" — 错误信息被吞

**没加护栏**：裸 `try/except` 只返回"服务不可用"，不区分超时/断连/格式错误。排查时只能看日志猜。

```python
# Before: 错误被吞
try:
    response = ollama.chat(...)
except Exception:
    reply = "服务不可用"  # 是超时？断连？不知道
```

**加 agent-fender**：

```python
# After: LLMResult.error_type 分类
result = await guard.safe_llm(ollama.chat, ...)
if not result.success:
    log.error(f"LLM fail: {result.error_type} - {result.error_message}")
    return {"final_reply": result.user_message}
    # error_type: "timeout" | "connection" | "response"
```

**防什么**：`LLMResult.error_type` 和 `SafeToolResult.error_type` 精确分类错误类型。可重试的（timeout）和不可重试的（connection）一目了然。
