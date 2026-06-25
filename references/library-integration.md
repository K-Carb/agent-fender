# Library Integration Guide

Full integration of the `agent_fender` library into an AI agent. Covers the 4-line API surface.

## Install

```bash
pip install git+https://github.com/Carb/agent-fender.git
```

## Setup

```python
from agent_fender import AgentGuard, GuardConfig

config = GuardConfig(
    max_loop_count=3,        # Max LLM→tool→LLM iterations
    max_tool_failures=2,     # Max consecutive tool failures before breaking
    dangerous_tools=frozenset({
        "delete_account", "cancel_order", "execute_command",
        "send_email", "write_file", "drop_table", "transfer_funds",
    }),
    llm_timeout_s=60.0,      # Per-LLM-call timeout
    tool_timeout_s=30.0,     # Per-tool-call timeout
    circuit_breaker_reply="Service temporarily unavailable.",
    llm_error_reply="Service temporarily unavailable.",
)

guard = AgentGuard(config)
```

## The 4 Integration Points

### 1. Loop Top: Circuit Breaker

```python
# BEFORE your agent loop (LangGraph node, CrewAI task, custom while loop):
breaker = guard.preflight(loop_count=state.loop_count, tool_failures=state.tool_failures)
if breaker.should_break:
    return {"final_reply": breaker.fallback_reply}
```

Place at the entry of every node or task that can loop. Pass the current iteration count and cumulative tool failure count.

### 2. LLM Call: Safe Wrapper

```python
# Replace:
#   response = await llm.chat(model="qwen", messages=[...], tools=[...])
# With:
result = await guard.safe_llm(
    llm.chat, model="qwen", messages=[...], tools=[...],
)
if not result.success:
    return {"final_reply": result.user_message}
response = result.data
```

- Handles both sync and async LLM callables
- Timeout from `config.llm_timeout_s` (override with `timeout_s=`)
- `result.error_type` is `"timeout"`, `"connection"`, or `"response"` — use for retry decisions

### 3. Before Tool Execution: Dangerous Tool Check

```python
# Before executing any tools:
tool_names = [tc["function"]["name"] for tc in response["message"]["tool_calls"]]
approval = guard.check_tools(tool_names)
if approval.requires_approval:
    # Trigger framework interrupt for human approval
    decision = interrupt(approval.message)
    if not decision:
        return {"final_reply": "Operation cancelled by user."}
```

Place between LLM response parsing and tool execution. Only tools in `config.dangerous_tools` trigger approval.

### 4. Tool Execution: Safe Wrapper

```python
# Replace:
#   result = await execute_tool(tool_name, tool_args)
# With:
tr = await guard.safe_tool(execute_tool, tool_name, tool_args)
if not tr.success:
    state.tool_failures += 1
    tr_result = tr.user_message
else:
    tr_result = tr.data
```

- Timeout from `config.tool_timeout_s` (override with `timeout_s=`)
- `tr.error_type` is `"timeout"` or `"execution_error"`

## Optional: Injection Detection

```python
# Before sending user input to LLM:
injection = guard.check_injection(user_input)
if injection.is_suspicious:
    return {"final_reply": "Your input contains suspicious patterns and cannot be processed."}
```

## Optional: Deduplication

```python
seen_keys: set[str] = set()

# At request entry:
dedup = guard.check_dedup(request_id, seen_keys)
if dedup.is_duplicate:
    return {"final_reply": "Duplicate request, already processed."}
```

## Optional: Audit Session

```python
# Start a structured audit session:
guard.start_session()

# ... agent runs with the 4 integration points above ...

# After agent completes:
session = guard.stop_session()
print(session.summary)
# GuardSession (12.3s):
#   LLM: 3 calls (1 timeout, 0 connection, 0 response)
#   Tools: 2 calls (0 timeout, 0 error)
#   Circuit breaker: ok
#   Approval: 1 checks, 1 required
#   Injection: 1 checks, 0 blocks
#   Dedup: 1 checks, 0 hits
```

`GuardSession` tracks every guarded call automatically when `guard.safe_llm()` and `guard.safe_tool()` are used. No manual instrumentation needed.

## Complete Integration Example

See `examples/minimal_agent.py` in the repository for a working end-to-end example with all 4 integration points.
