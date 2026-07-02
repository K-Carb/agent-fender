# Inline Guard Patterns (No Library)

Minimal, dependency-free implementations of the 6 agent guards. Copy only the guards that are missing from the user's code. Never generate all 6 unless all 6 are absent.

## Guard 1: LLM Timeout + Error Classification

```python
import asyncio

async def safe_llm(llm_call, *, timeout=60, fallback="Service temporarily unavailable", **kwargs):
    if asyncio.iscoroutinefunction(llm_call):
        coro = llm_call(**kwargs)
    else:
        coro = asyncio.to_thread(llm_call, **kwargs)
    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
        return {"success": True, "data": result}
    except asyncio.TimeoutError:
        return {"success": False, "error_type": "timeout", "user_message": fallback}
    except Exception as exc:
        error_type = "connection" if "connect" in str(exc).lower() else "response"
        return {"success": False, "error_type": error_type, "error_message": str(exc), "user_message": fallback}
```

Key points:
- Handles both sync and async callables via `inspect.iscoroutinefunction`
- Classifies errors into `timeout`, `connection`, `response` — not one catch-all
- Returns structured result, never raises

## Guard 2: Loop Limit

```python
MAX_LOOPS = 5

loop_count = 0
while loop_count < MAX_LOOPS:
    loop_count += 1
    # ... LLM call + tool execution ...
else:
    # Loop exhausted — return fallback
    return {"final_reply": "Service temporarily unavailable."}
```

Key points:
- `while` loop with explicit counter, never `while True`
- `else` block handles exhaustion gracefully
- For graph-based agents (LangGraph), check `loop_count >= MAX_LOOPS` at the entry of every node that can loop

## Guard 3: Tool Timeout + Error Classification

```python
async def safe_tool(tool_func, *args, timeout=30, **kwargs):
    if asyncio.iscoroutinefunction(tool_func):
        coro = tool_func(*args, **kwargs)
    else:
        coro = asyncio.to_thread(tool_func, *args, **kwargs)
    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
        return {"success": True, "data": result}
    except asyncio.TimeoutError:
        return {"success": False, "error_type": "timeout", "user_message": "Operation timed out."}
    except Exception as exc:
        return {"success": False, "error_type": "execution_error", "error_message": str(exc), "user_message": "Operation failed."}
```

## Guard 4: Dangerous Tool Gating

```python
DANGEROUS_TOOLS = frozenset({
    "delete_account", "delete_file", "execute_command",
    "send_email", "write_file", "drop_table", "transfer_funds",
})

def check_dangerous(tool_names):
    matched = [t for t in tool_names if t in DANGEROUS_TOOLS]
    if matched:
        return {
            "requires_approval": True,
            "dangerous_tools_found": matched,
            "message": f"Approval required: {', '.join(matched)}"
        }
    return {"requires_approval": False, "dangerous_tools_found": []}

# Usage:
approval = check_dangerous(["search_files", "delete_file"])
if approval["requires_approval"]:
    raise Interrupt(approval["message"])  # Or your framework's interrupt mechanism
```

Key points:
- `DANGEROUS_TOOLS` must be configured per application — the list above is a starting point
- The check happens BEFORE tool execution, not after
- The interrupt mechanism depends on the framework (LangGraph `interrupt()`, CrewAI `ask_human()`, etc.)

## Guard 5: Injection Detection

```python
import re

INJECTION_PATTERNS = [
    (r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", "high"),
    (r"pretend\s+(you\s+are|to\s+be)", "medium"),
    (r"forget\s+(everything|all|your\s+training)", "high"),
    (r"system\s*(prompt|message|instruction)\s*(is|:)", "high"),
    (r"\[system\]|<<system>>|\{system\}", "high"),
    (r"new\s+instructions?\s*(:|=)", "medium"),
    (r"disregard\s+(all\s+)?(previous|prior)", "high"),
    (r"from\s+now\s+on\s+you\s+(are|will\s+be)", "low"),
]

def check_injection(text):
    matched = []
    highest_risk = "low"
    risk_order = {"low": 0, "medium": 1, "high": 2}
    for pattern, risk in INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            matched.append(pattern)
            if risk_order[risk] > risk_order[highest_risk]:
                highest_risk = risk
    return {
        "is_suspicious": len(matched) > 0,
        "patterns_matched": matched,
        "risk": highest_risk,
    }
```

Key points:
- Regex-based detection is a baseline, not a complete solution
- Reports which patterns matched and the highest risk level
- Custom patterns can be added for domain-specific injection vectors

## Guard 6: Audit Trail

```python
import time
import json

class AuditTrail:
    def __init__(self):
        self.records = []
        self.started_at = time.time()

    def log(self, event_type, success, detail=""):
        self.records.append({
            "time": time.time(),
            "event": event_type,
            "success": success,
            "detail": detail,
        })

    def summary(self):
        total = len(self.records)
        errors = sum(1 for r in self.records if not r["success"])
        elapsed = time.time() - self.started_at
        return f"{total} events, {errors} errors, {elapsed:.1f}s"

    def to_json(self):
        return json.dumps({
            "summary": self.summary(),
            "records": self.records,
        }, indent=2, ensure_ascii=False)
```

Key points:
- Tracks every LLM call, tool call, approval check, and injection scan
- `summary()` for quick diagnosis, `to_json()` for export
- Integrate into the agent loop: call `audit.log("llm_call", result.success)` after each operation

## Guard 7: Token Budget Control

```python
TOKEN_BUDGET = 100_000  # Max tokens per invocation (0 = disabled)

def count_tokens(text):
    """Approximate token count: 4 chars ≈ 1 English token."""
    return len(text) // 4

# Usage — accumulate across LLM calls and check before each iteration:
tokens_used = 0

while loop_count < MAX_LOOPS:
    # ... LLM call ...
    response = await llm.chat(messages=[...], tools=[...])
    tokens_used += count_tokens(str(response))

    # Check BEFORE the next LLM call
    if TOKEN_BUDGET > 0 and tokens_used >= TOKEN_BUDGET:
        return {"final_reply": "Token budget exceeded."}

    loop_count += 1
```

Key points:
- Set `TOKEN_BUDGET` per invocation — the agent stops when accumulated tokens hit the limit
- Check BEFORE the next LLM call, not after — prevents one last expensive call
- `len(text)//4` is a conservative approximation for English; use tiktoken for precise counting
- Token budget complements loop limit — they address different dimensions of the same problem
