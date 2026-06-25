---
name: agent-fender
description: Agent runtime safety guardrails. Audits AI agent code for missing timeout, circuit breaker, injection detection, dangerous tool approval, dedup, and audit logging. Use when writing, reviewing, or debugging any AI agent code (LangGraph, CrewAI, AutoGen, OpenAI function calling, or custom loops).
---

# Agent Fender

Agent 运行时安全护栏。6 条规则，覆盖从 LLM 调用到工具执行的完整生命周期。

## When to Activate

Activate when any of these are true:

- User is writing or reviewing AI Agent code (any framework or custom loop)
- Code contains LLM calls, tool calls, or agent loops (`while True`, `for _ in range`, graph edges)
- User mentions: agent, LLM, tool calling, function calling, LangGraph, CrewAI, AutoGen, OpenAI tools, MCP tool, LangChain
- User asks: "check my agent", "audit my agent", "is my agent safe", "agent keeps failing", "agent stuck in loop", "agent timeout"
- User says they want to deploy or ship an agent

## The 6 Rules

Every AI agent, regardless of framework or use case, must have:

| # | Rule | Check For |
|---|------|-----------|
| 1 | **LLM timeout + error classification** | Every LLM call wrapped in timeout. Errors classified as timeout/connection/response (not bare `except Exception`). |
| 2 | **Loop limit** | Every agent loop has a maximum iteration cap. No unbounded `while True`. |
| 3 | **Tool timeout + error classification** | Every tool execution wrapped in timeout. Errors classified as timeout/execution_error. |
| 4 | **Dangerous tool gating** | Write/delete/execute/send operations intercepted before execution. Human approval required for dangerous actions. |
| 5 | **Injection detection** | User input scanned for prompt injection patterns before reaching the LLM. |
| 6 | **Audit trail** | Structured tracking of LLM calls, tool calls, errors, and decisions. Not just print statements. |

## Behavior Modes

### Audit Mode

When user asks to audit or check agent code:

1. Read the agent code
2. Check each of the 6 rules
3. Report findings:

```
## Agent Safety Audit

| Rule | Status | Detail |
|------|--------|--------|
| 1. LLM timeout | ✗ Missing | Line 23: ollama.chat() has no timeout |
| 2. Loop limit | ✓ Present | Line 15: loop_count < MAX_ITER |
| 3. Tool timeout | ✗ Missing | Line 45: execute_tool() has no timeout |
| 4. Dangerous tool gating | ✗ Missing | No approval check before cancel_order |
| 5. Injection detection | ✗ Missing | User input goes directly to LLM |
| 6. Audit trail | ✗ Partial | print() statements, no structured logging |

Coverage: 1/6  →  Fix the 5 missing guards.
```

4. If missing guards are found, offer to fix them.

### Fix Mode

When user wants to fix missing guards, present two options:

**Option A: Install the library** (recommended for production)
```bash
pip install git+https://github.com/Carb/agent-fender.git
```
Then integrate with 4 lines:
```python
from agent_fender import AgentGuard, GuardConfig

guard = AgentGuard(GuardConfig(
    max_loop_count=3,
    max_tool_failures=2,
    dangerous_tools=frozenset({"delete_", "cancel_", "execute_"}),
))

# Replace llm_call(...) with:
result = await guard.safe_llm(llm_call, ...)

# Replace tool_exec(...) with:
result = await guard.safe_tool(tool_exec, ...)

# Add at loop top:
if guard.preflight(loop_count=n, tool_failures=f).should_break:
    return fallback_response

# Add before tool execution:
if guard.check_tools(tool_names).requires_approval:
    await request_human_approval()
```

**Option B: Inline patterns** (no dependency)
Generate minimal inline implementations of the missing guards directly in the user's code.

### Generate Mode

When generating new agent code from scratch, automatically include all 6 guards:

- If the user accepts the library: generate code using `agent_fender`
- If the user prefers no dependency: generate inline guard patterns
- Never generate bare agent code without guards unless the user explicitly asks for a minimal demo

## Guard Code Patterns (Inline, No Library)

When the user chooses Option B (no dependency), use these minimal patterns:

### Rule 1: LLM timeout
```python
import asyncio

async def safe_llm(llm_call, timeout=60, **kwargs):
    try:
        return await asyncio.wait_for(llm_call(**kwargs), timeout=timeout)
    except asyncio.TimeoutError:
        return {"error": "timeout", "user_message": "Service temporarily unavailable"}
    except Exception as e:
        error_type = "connection" if "connect" in str(e).lower() else "response"
        return {"error": error_type, "user_message": "Service temporarily unavailable"}
```

### Rule 2: Loop limit
```python
MAX_LOOPS = 5
loop_count = 0
while loop_count < MAX_LOOPS:
    loop_count += 1
    ...
```

### Rule 3: Tool timeout
```python
async def safe_tool(tool_func, *args, timeout=30, **kwargs):
    try:
        return await asyncio.wait_for(tool_func(*args, **kwargs), timeout=timeout)
    except asyncio.TimeoutError:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": "execution_error", "detail": str(e)}
```

### Rule 4: Dangerous tool gating
```python
DANGEROUS = {"delete_", "cancel_", "execute_", "write_", "send_"}

def check_dangerous(tool_names):
    matched = [t for t in tool_names if any(t.startswith(d) for d in DANGEROUS)]
    if matched:
        return {"requires_approval": True, "tools": matched}
    return {"requires_approval": False}
```

### Rule 5: Injection detection
```python
import re

INJECTION_PATTERNS = [
    (r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", "high"),
    (r"pretend\s+(you\s+are|to\s+be)", "medium"),
    (r"forget\s+(everything|all|your\s+training)", "high"),
    (r"\[system\]|<<system>>|\{system\}", "high"),
]

def check_injection(text):
    for pattern, risk in INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return {"is_suspicious": True, "risk": risk}
    return {"is_suspicious": False}
```

### Rule 6: Audit trail
```python
import time, json

class AuditTrail:
    def __init__(self):
        self.records = []
        self.started_at = time.time()

    def log(self, event_type, success, detail=""):
        self.records.append({
            "time": time.time(), "event": event_type,
            "success": success, "detail": detail
        })

    def summary(self):
        errors = [r for r in self.records if not r["success"]]
        return f"{len(self.records)} events, {len(errors)} errors"

    def to_json(self):
        return json.dumps(self.records, indent=2, ensure_ascii=False)
```

## Important

- This skill covers **runtime safety** for agent execution, not code quality or testing
- Always offer both Option A (library) and Option B (inline) — let the user choose
- The library (`agent-fender`) provides more thorough implementations with edge cases handled
- Inline patterns are minimal — they cover the 80% case, not every edge case
- Never claim an agent is "safe" — say "all 6 guards are present" instead
