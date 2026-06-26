---
name: agent-fender
description: This skill should be used when writing, reviewing, or debugging AI agent code. Covers runtime safety guardrails: LLM timeout, loop limit, tool timeout, dangerous-tool gating, injection detection, and audit trail. Activate when user mentions agent, LLM, tool calling, LangGraph, CrewAI, AutoGen, OpenAI tools, or asks to "audit my agent", "check my agent for safety", "add guardrails", or "why is my agent failing".
---

# Agent Fender

## The Iron Law

```
EVERY AI AGENT MUST HAVE 6 GUARDS. MISSING EVEN ONE IS A BUG, NOT A FEATURE GAP.
```

Agent code without these guards is incomplete — regardless of how well the business logic works. Errors without classification, loops without limits, and user input without inspection are not "future improvements." They are defects that will surface in production.

## The 6 Guards

| # | Guard | What to Verify | Severity |
|---|-------|---------------|----------|
| 1 | **LLM timeout + error classification** | Every LLM call has timeout. Errors classified as `timeout` / `connection` / `response`. No bare `except Exception`. | Critical |
| 2 | **Loop limit** | Every agent loop has a maximum iteration cap. No unbounded `while True` or unbounded graph recursion. | Critical |
| 3 | **Tool timeout + error classification** | Every tool execution has timeout. Errors classified as `timeout` / `execution_error`. | Critical |
| 4 | **Dangerous tool gating** | Write/delete/execute/send operations intercepted before execution. Human approval gate for dangerous actions. | High |
| 5 | **Injection detection** | User-supplied text scanned for prompt injection patterns before reaching the LLM. | High |
| 6 | **Audit trail** | Structured tracking of LLM calls, tool calls, errors, and decisions. Not `print()` statements. | Medium |

## When to Activate

Activate when the user's request involves agent code and any of:

- **Writing**: generate agent, build agent, create a LangGraph/CrewAI/AutoGen agent
- **Reviewing**: audit agent, check agent safety, review this agent code, is my agent safe
- **Debugging**: agent keeps failing, agent stuck in loop, agent timeout, agent hangs, agent bill too high
- **Frameworks**: LangGraph, CrewAI, AutoGen, OpenAI function calling / tools, MCP tool, LangChain
- **Patterns**: `while True` + LLM call, tool execution without try/except, bare `requests.post` in agent code

## Behavior

### Audit Mode

When the user provides agent code to audit:

1. Read the full agent source
2. Check each of the 6 guards against the actual code
3. Report findings in this exact format:

```
## Agent Safety Audit

| # | Guard | Status | Detail |
|---|-------|--------|--------|
| 1 | LLM timeout | ✗ | Line 23: ollama.chat() has no timeout |
| 2 | Loop limit | ✓ | Line 15: loop_count < MAX_ITER |
| 3 | Tool timeout | ✗ | Line 45: execute_tool() has no timeout |
| 4 | Dangerous tool gating | ✗ | No approval check before delete_record |
| 5 | Injection detection | ✗ | User input goes directly to LLM |
| 6 | Audit trail | ✗ | print() only, no structured logging |

Coverage: 1/6 — 5 guards missing.
```

4. If any guards are missing, offer to fix them (see Fix Mode)

### Fix Mode

Present two options and let the user choose:

**Option A: Use the `agent_fender` library** — production-ready, zero dependencies.

```bash
pip install git+https://github.com/Carb/agent-fender.git
```

Integration: wrap LLM calls with `fender.safe_llm()`, tool calls with `fender.safe_tool()`, add `fender.preflight()` at loop top, add `fender.check_tools()` before tool execution. See `references/library-integration.md` for the full 4-line integration pattern.

**Option B: Inline guard patterns** — no dependency, minimal implementations.

Generate only the missing guards directly in the user's code. See `references/inline-patterns.md` for canonical implementations of all 6 guards. Copy only what's missing; never generate all 6 if only 2 are needed.

### Generate Mode

When generating new agent code from scratch, include all 6 guards by default. Offer the user the choice between library-based and inline-based code. Never generate bare agent code without guards unless the user explicitly asks for a minimal demo or prototype.

## Red Flags

If any of these thoughts occur, STOP and apply the 6-guard check:

- "This agent is simple, it doesn't need guards"
- "The user didn't ask for safety, just build the agent"
- "I'll add error handling later"
- "The framework probably handles this"
- "Just a prototype, skip the guards"

Framework built-in features do not replace these guards. LangGraph checkpointing is not an audit trail. CrewAI retry is not tool timeout + error classification. AutoGen's max_turns is not loop limit — it only limits turns, not LLM calls per turn.

## Guard Quick Reference

| Guard | Ask | Quick Fix |
|-------|-----|-----------|
| 1. LLM timeout | Is every LLM call wrapped in timeout? | `asyncio.wait_for(llm_call(**kwargs), timeout=60)` |
| 2. Loop limit | Is there a max iteration cap? | `while loop_count < MAX_LOOPS:` |
| 3. Tool timeout | Is every tool call wrapped in timeout? | `asyncio.wait_for(tool_func(*args, **kwargs), timeout=30)` |
| 4. Dangerous gating | Are write/delete/execute operations intercepted? | `if tool_name in DANGEROUS: ask_approval()` |
| 5. Injection scan | Is user input scanned before reaching the LLM? | `if check_injection(user_text): block()` |
| 6. Audit trail | Can you trace what happened after a failure? | Structured log with event types and error classification |

## Scope

This skill covers **runtime safety** for agent execution. It does not cover:

- Output content safety (use a moderation API for that)
- Token cost optimization (complementary concern)
- Code quality or testing practices
- Framework-specific configuration

## References

Detailed implementations and patterns live in:

- **`references/inline-patterns.md`** — Minimal inline implementations of all 6 guards (no dependency)
- **`references/library-integration.md`** — Full `agent_fender` library integration guide with examples
- **`references/audit-examples.md`** — Annotated audit results for common agent patterns
