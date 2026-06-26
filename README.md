# agent-fender

> **AI wrote your agent code. Who checked it for 6 critical safety gaps?**
> agent-fender did. And if we found gaps, the companion library patches them in 4 lines.

![Tests](https://github.com/Carb/agent-fender/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## Quick Start (Skill — Recommended)

1. Copy the skill into your agent project:
   ```bash
   # From your agent project root:
   mkdir -p .claude/skills/agent-fender
   cp SKILL.md .claude/skills/agent-fender/
   cp -r references/ .claude/skills/agent-fender/
   ```

2. Open Claude Code in that project. Say:
   > "audit my agent code for safety gaps"

3. You'll get a report card like:
   ```
   ## Agent Safety Audit
   | # | Guard          | Status | Detail                              |
   |---|----------------|--------|-------------------------------------|
   | 1 | LLM timeout    | ✗      | Line 23: ollama.chat() has no timeout |
   | 2 | Loop limit     | ✓      | Line 15: loop_count < MAX_ITER       |
   | 3 | Tool timeout   | ✗      | Line 45: execute_tool() has no timeout|
   | 4 | Dangerous tools| ✗      | No approval before delete_record     |
   | 5 | Injection scan | ✗      | User input goes directly to LLM      |
   | 6 | Audit trail    | ✗      | print() only, no structured logging   |

   Coverage: 1/6 — 5 guards missing.
   ```

4. Fix them by choosing:
   - **Option A**: `pip install git+https://github.com/Carb/agent-fender.git` — production-ready, zero deps (see below)
   - **Option B**: Copy inline guard patterns — no dependency (see [references/inline-patterns.md](references/inline-patterns.md))

---

## Quick Start (Library — Standalone)

```bash
pip install git+https://github.com/Carb/agent-fender.git
```

```python
import asyncio
from agent_fender import AgentFender, FenderConfig

config = FenderConfig(
    max_loop_count=3,
    max_tool_failures=2,
    dangerous_tools=frozenset({"delete_file", "drop_table"}),
    llm_timeout_s=60.0,
    tool_timeout_s=30.0,
)
fender = AgentFender(config)

# Replace these with your real LLM and tool functions
async def my_llm(**kwargs):
    return {"message": {"content": "Response from LLM"}}

def my_tool(name, args):
    return f"Tool {name} completed"

async def main():
    # 1. Circuit breaker — prevents infinite loops
    breaker = fender.preflight(loop_count=2, tool_failures=0)
    if breaker.should_break:
        return breaker.fallback_reply

    # 2. Safe LLM — timeout + error classification
    result = await fender.safe_llm(my_llm, messages=[{"role": "user", "content": "hi"}])
    if not result.success:
        return result.user_message  # error_type: timeout | connection | response

    # 3. Dangerous tool gating — intercept before execution
    approval = fender.check_tools(["delete_file"])
    if approval.requires_approval:
        print(f"Approval needed: {approval.message}")

    # 4. Safe tool — timeout + error classification
    tr = await fender.safe_tool(my_tool, "search_files", '{"query": "*.log"}')
    print(f"Tool result: {tr.data}")

asyncio.run(main())
```

---

## What Problems Does This Solve?

| Developer says               | Root cause                        | agent-fender component |
|------------------------------|-----------------------------------|------------------------|
| "Why is it spinning forever?" | LLM or tool has no timeout        | `safe_llm()` + `safe_tool()` |
| "Why is my bill so high?"    | Agent loops infinitely            | `preflight()` loop_count |
| "Why was that file deleted?" | Dangerous tool ran silently     | `check_tools()` |
| "Why does it keep retrying after failure?" | Tool failures accumulate | `preflight()` tool_failures |
| "Why does it work sometimes and not others?" | Errors swallowed without classification | `LLMResult.error_type` |

Full failure mode catalog: [docs/failure-modes.md](docs/failure-modes.md)

---

## The 6 Guards

| # | Guard                        | Severity | What it does                                          |
|---|------------------------------|----------|-------------------------------------------------------|
| 1 | LLM timeout + error classification | Critical | Every LLM call has a timeout; errors are `timeout` / `connection` / `response` |
| 2 | Loop limit                   | Critical | Every agent loop has a max iteration cap              |
| 3 | Tool timeout + error classification | Critical | Every tool call has a timeout; errors are `timeout` / `execution_error` |
| 4 | Dangerous tool gating        | High     | Write/delete/execute operations intercepted before execution |
| 5 | Injection detection          | High     | User input scanned for prompt injection patterns before reaching the LLM |
| 6 | Audit trail                  | Medium   | Structured tracking of all calls, errors, and decisions |

---

## Design Principles

- **Zero dependencies** — pure Python stdlib. No LangGraph, no Pydantic, no Ollama lock-in.
- **Pure functions** — every component is independently testable. No framework graph required.
- **Result pattern** — all return values are dataclasses. AI copilots understand the type signatures.
- **Facade API** — `AgentFender` provides a 4-step API covering the full agent lifecycle.
- **Skill-first distribution** — the Claude Code skill finds problems; the library fixes them.

---

## How This Compares

agent-fender is the only library that combines all 6 guards in one zero-dependency package, AND the only one with a Claude Code skill for agent code auditing.

| Feature                    | agent-fender | agentguard-llm | Aura Guard |
|----------------------------|:-----------:|:--------------:|:----------:|
| Zero dependencies           | ✅ | ✅ | ✅ |
| Circuit breaker             | ✅ | ✅ | ✅ |
| LLM timeout + classification | ✅ | ✅ | ? |
| Tool timeout + classification | ✅ | ✅ | ? |
| Dangerous tool gating       | ✅ | ❌ | ✅ |
| Injection detection         | ✅ | ❌ | ❌ |
| Deduplication               | ✅ | ✅ | ✅ |
| Audit trail                 | ✅ | ✅ | ✅ |
| Retry with backoff          | ✅ | ✅ | ❌ |
| Budget enforcement          | ❌ | ✅ | ❌ |
| **Claude Code skill**       | ✅ | ❌ | ❌ |
| **Code audit (push model)** | ✅ | ❌ | ❌ |

agent-fender's unique advantage is the **skill-library combination**: the skill finds your agent's safety gaps during development, and the library fixes them with all 6 guards in one package. Other libraries wait for you to find them on PyPI.

AI tools can generate guard code in seconds. But generated code has no tests, no edge case coverage, no guarantee it catches all 6 gaps. agent-fender ships 106 tests across every guard — certainty, not just code.

---

## Real-World Usage

See [`examples/`](examples/) for framework integration patterns with LangGraph, CrewAI, and AutoGen — each runs without API keys and demonstrates all 4 integration points.

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/failure-modes.md](docs/failure-modes.md) | 7 real-world agent failure scenarios and how agent-fender prevents each |
| [references/library-integration.md](references/library-integration.md) | Full 4-step integration guide for the Python library |
| [references/inline-patterns.md](references/inline-patterns.md) | Minimal inline guard implementations (no dependency) |
| [references/audit-examples.md](references/audit-examples.md) | Annotated audit results for 3 common agent patterns |
| [examples/minimal_agent.py](examples/minimal_agent.py) | Working end-to-end example |
| [examples/](examples/) | Framework integration examples: LangGraph, CrewAI, AutoGen |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT
