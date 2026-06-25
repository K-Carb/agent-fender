# Audit Examples

Annotated audit results for three common agent code patterns. Use as reference when interpreting audit findings.

## Example 1: Bare LangGraph Agent (0/6)

```python
# User's code:
class AgentState(TypedDict):
    messages: list
    loop_count: int

async def action_node(state: AgentState):
    response = ollama.chat(model="qwen", messages=state["messages"], tools=[...])
    tool_calls = response["message"]["tool_calls"]
    for tc in tool_calls:
        result = execute_tool(tc["function"]["name"], eval(tc["function"]["arguments"]))
        state["messages"].append({"role": "tool", "content": str(result)})
    return state
```

Audit result:

```
## Agent Safety Audit

| # | Guard | Status | Detail |
|---|-------|--------|--------|
| 1 | LLM timeout | ✗ | ollama.chat() has no timeout; errors not classified |
| 2 | Loop limit | ✗ | state.loop_count is tracked but never checked against a max |
| 3 | Tool timeout | ✗ | execute_tool() has no timeout; no error classification |
| 4 | Dangerous tool gating | ✗ | All tool calls execute immediately without approval check |
| 5 | Injection detection | ✗ | User messages in state["messages"] go directly to LLM |
| 6 | Audit trail | ✗ | No structured logging of calls or errors |

Coverage: 0/6 — all 6 guards missing.
```

## Example 2: Agent With Partial Guards (2/6)

```python
# User's code — they added some guards but missed others:
MAX_ITER = 5

async def agent_loop():
    loop_count = 0
    while loop_count < MAX_ITER:
        loop_count += 1
        try:
            response = await asyncio.wait_for(
                llm.chat(messages=[...], tools=[...]), timeout=60
            )
        except asyncio.TimeoutError:
            return "Request timed out."
        except Exception:
            return "Something went wrong."

        for tc in response["message"]["tool_calls"]:
            result = execute_tool(tc.name, tc.args)
            print(f"Tool {tc.name}: {result}")
```

Audit result:

```
## Agent Safety Audit

| # | Guard | Status | Detail |
|---|-------|--------|--------|
| 1 | LLM timeout | ✓ | asyncio.wait_for with 60s timeout. Error classification: partial — has timeout case but general Exception is too broad |
| 2 | Loop limit | ✓ | MAX_ITER = 5 enforced |
| 3 | Tool timeout | ✗ | execute_tool() has no timeout; no error classification |
| 4 | Dangerous tool gating | ✗ | All tools execute without approval |
| 5 | Injection detection | ✗ | User input not scanned |
| 6 | Audit trail | △ | print() only — unstructured, not exportable, no error types |

Coverage: 2/6 (1 partial). Fix guards 3, 4, 5, and 6.
```

## Example 3: Well-Guarded Agent (6/6)

```python
# User's code — all 6 guards present:
from agent_fender import AgentGuard, GuardConfig

guard = AgentGuard(GuardConfig(max_loop_count=5, max_tool_failures=3,
                                dangerous_tools=frozenset({"delete_account"})))

async def agent_loop():
    guard.start_session()
    loop_count = 0
    tool_failures = 0

    while True:
        # Guard 2: loop limit via preflight
        breaker = guard.preflight(loop_count=loop_count, tool_failures=tool_failures)
        if breaker.should_break:
            return breaker.fallback_reply
        loop_count += 1

        # Guard 5: injection detection
        user_input = get_latest_user_message(state)
        if guard.check_injection(user_input).is_suspicious:
            return "Suspicious input detected."

        # Guard 1: safe LLM
        llm_result = await guard.safe_llm(llm.chat, model="qwen", messages=[...], tools=[...])
        if not llm_result.success:
            return llm_result.user_message

        tool_names = [tc["function"]["name"] for tc in llm_result.data["message"]["tool_calls"]]

        # Guard 4: dangerous tool gating
        if guard.check_tools(tool_names).requires_approval:
            if not await request_human_approval():
                return "Operation cancelled."

        for name in tool_names:
            # Guard 3: safe tool
            tr = await guard.safe_tool(execute_tool, name, args)
            if not tr.success:
                tool_failures += 1

        # Guard 6: audit trail (automatic via guard session)
```

Audit result:

```
## Agent Safety Audit

| # | Guard | Status | Detail |
|---|-------|--------|--------|
| 1 | LLM timeout | ✓ | guard.safe_llm() with 60s timeout; errors classified as timeout/connection/response |
| 2 | Loop limit | ✓ | guard.preflight() checks loop_count >= 5 |
| 3 | Tool timeout | ✓ | guard.safe_tool() with 30s timeout; errors classified as timeout/execution_error |
| 4 | Dangerous tool gating | ✓ | guard.check_tools() intercepts delete_account before execution |
| 5 | Injection detection | ✓ | guard.check_injection() scans user input before LLM |
| 6 | Audit trail | ✓ | GuardSession tracks all calls, errors, and decisions |

Coverage: 6/6 — all guards present.
```
