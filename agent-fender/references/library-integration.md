# Library Integration Guide

Full integration of the `agent_fender` library into an AI agent. Covers the 4-line API surface.

## Install

```bash
pip install git+https://github.com/K-Carb/agent-fender.git
```

## Setup

```python
from agent_fender import AgentFender, FenderConfig

config = FenderConfig(
    max_loop_count=3,        # Max LLM→tool→LLM iterations
    max_tool_failures=2,     # Max consecutive tool failures before breaking
    dangerous_tools=frozenset({
        "delete_account", "delete_file", "execute_command",
        "send_email", "write_file", "drop_table", "transfer_funds",
    }),
    llm_timeout_s=60.0,      # Per-LLM-call timeout
    tool_timeout_s=30.0,     # Per-tool-call timeout
    circuit_breaker_reply="Service temporarily unavailable.",
    llm_error_reply="Service temporarily unavailable.",
)

fender = AgentFender(config)
```

## The 4 Integration Points

### 1. Loop Top: Circuit Breaker

```python
# BEFORE your agent loop (LangGraph node, CrewAI task, custom while loop):
breaker = fender.preflight(loop_count=state.loop_count, tool_failures=state.tool_failures)
if breaker.should_break:
    return {"final_reply": breaker.fallback_reply}
```

Place at the entry of every node or task that can loop. Pass the current iteration count and cumulative tool failure count.

### 2. LLM Call: Safe Wrapper

```python
# Replace:
#   response = await llm.chat(model="qwen", messages=[...], tools=[...])
# With:
result = await fender.safe_llm(
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
approval = fender.check_tools(tool_names)
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
tr = await fender.safe_tool(execute_tool, tool_name, tool_args)
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
injection = fender.check_injection(user_input)
if injection.is_suspicious:
    return {"final_reply": "Your input contains suspicious patterns and cannot be processed."}
```

## Optional: Deduplication

```python
seen_keys: set[str] = set()

# At request entry:
dedup = fender.check_dedup(request_id, seen_keys)
if dedup.is_duplicate:
    return {"final_reply": "Duplicate request, already processed."}
```

## Optional: Token Budget Control

```python
# Set a token budget in config:
config = FenderConfig(token_budget=100_000)  # 100K token limit

# Accumulate tokens across LLM calls:
tokens_used = 0
for iteration in range(max_loops):
    result = await fender.safe_llm(llm.chat, messages=[...])
    if result.success:
        tokens_used += fender.count_tokens(str(result.data))

    # Token budget checked in preflight before next LLM call:
    breaker = fender.preflight(
        loop_count=iteration,
        tool_failures=failures,
        tokens_used=tokens_used,
    )
    if breaker.should_break:
        return {"final_reply": breaker.fallback_reply}
```

- Default counting: `len(text) // 4` (approximate, 4 chars ≈ 1 English token)
- For precise counting, pass `token_counter=your_tiktoken_counter` to `FenderConfig`
- `token_budget=0` (default) disables the budget check — fully backward compatible
- `CircuitBreakerResult.reason == "token_budget"` when the budget is exceeded

## Optional: Audit Session

```python
# Start a structured audit session:
fender.start_session()

# ... agent runs with the 4 integration points above ...

# After agent completes:
session = fender.stop_session()
print(session.summary)
# FenderSession (12.3s):
#   LLM: 3 calls (1 timeout, 0 connection, 0 response)
#   Tools: 2 calls (0 timeout, 0 error)
#   Circuit breaker: ok
#   Approval: 1 checks, 1 required
#   Injection: 1 checks, 0 blocks
#   Dedup: 1 checks, 0 hits
```

`FenderSession` tracks every guarded call automatically when `fender.safe_llm()` and `fender.safe_tool()` are used. No manual instrumentation needed.

## Complete Integration Example

See `examples/minimal_agent.py` in the repository for a working end-to-end example with all 4 integration points.
