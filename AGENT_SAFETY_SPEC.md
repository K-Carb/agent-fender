# Agent Safety Specification

**Version:** 1.0.0
**Status:** Stable

---

## What This Is

This document defines the standard for AI agent code safety. It specifies the minimum set of runtime guards every AI agent must have, why each is required, and how to verify compliance.

It is **platform-independent** — it does not reference any specific AI coding assistant, framework, or implementation. Platform adapters (Claude Code skill, Cursor rules, CI scanners, runtime libraries) derive their behavior from this spec.

---

## The Iron Law

```
EVERY AI AGENT MUST HAVE 7 GUARDS.
MISSING EVEN ONE IS A DEFECT, NOT A FEATURE GAP.
```

AI agents execute LLM calls and tool operations in loops. Without guards, they fail silently, expensively, and repeatedly. These 7 guards are not optional safety features — they are the minimum completeness bar for any agent that runs in production.

---

## The 7 Guards

### Guard 1: LLM Timeout + Error Classification

**Severity:** Critical

**What it is:** Every call to an LLM must have an explicit timeout. Failures must be classified into distinct error types — not generic `except Exception`.

**Why:** LLM APIs hang. Networks drop. Providers return malformed responses. An unguarded LLM call can block an agent indefinitely. When it fails, the agent needs to know *how* it failed to decide what to do next: retry (timeout), fall back (connection error), or report to the user (response error).

**Verification criteria:**
- Every LLM call site is wrapped in a timeout mechanism
- Errors are classified into at least three types: `timeout`, `connection`, `response`
- No bare `except Exception` or `except Exception as e` in LLM call paths
- Failed calls return structured results, not raised exceptions

---

### Guard 2: Loop Limit

**Severity:** Critical

**What it is:** Every agent execution loop must have an explicit maximum iteration cap. There must be no path through the agent that can iterate without bound.

**Why:** An LLM can repeatedly select tools without converging. Each iteration burns tokens and time. Without a cap, the agent continues until the developer kills the process or the API bill forces attention. The loop limit is the last line of defense when all other convergence mechanisms fail.

**Verification criteria:**
- Every `while` loop in agent execution paths has a counter that increments and a bound it checks
- Every graph/state-machine-based agent has a max step or max recursion limit
- Framework-level recursion limits (LangGraph `recursion_limit`, CrewAI `max_iter`) are explicitly set, not left at defaults
- The limit is enforced at the top of each iteration, before any LLM or tool call

---

### Guard 3: Tool Timeout + Error Classification

**Severity:** Critical

**What it is:** Every tool execution call must have an explicit timeout. Failures must be classified — at minimum, distinguishing between timeout and execution error.

**Why:** Tools talk to databases, APIs, file systems. Any of these can hang. A hung tool call blocks the agent just as effectively as a hung LLM call. And unlike LLM failures, tool failures often cascade — a hung database query means subsequent queries queue up, connections exhaust, the entire agent process degrades.

**Verification criteria:**
- Every tool execution call site is wrapped in a timeout mechanism
- Errors are classified into at least two types: `timeout`, `execution_error`
- Tool failures do not crash the agent — they return structured error results
- Consecutive tool failures are tracked for circuit breaker purposes (see Guard 2)

---

### Guard 4: Dangerous Tool Gating

**Severity:** High

**What it is:** Tools that perform write, delete, execute, or send operations must be explicitly approved before execution. The agent must not invoke these tools silently.

**Why:** LLMs can hallucinate tool calls. A user asking "What was my last order?" should never result in `cancel_order()` being called. Even when the LLM correctly identifies the right tool, a dangerous action must not execute without a human in the loop — or at minimum, an explicit allowlist check.

**Verification criteria:**
- Write/delete/execute/send operations are intercepted before execution
- A human approval gate or programmatic allowlist check exists between tool selection and tool execution
- The set of dangerous tools is explicitly defined (not inferred)
- The approval check happens *after* tool selection but *before* tool execution

---

### Guard 5: Injection Detection

**Severity:** High

**What it is:** All user-supplied text that flows into an LLM prompt must be scanned for prompt injection patterns before reaching the model.

**Why:** Agent applications accept untrusted input — chat messages, uploaded documents, API payloads. This input is concatenated into LLM prompts. Without scanning, an attacker can inject instructions that override system prompts, exfiltrate conversation history, or trigger unauthorized tool calls.

**Verification criteria:**
- Every path from user input to LLM prompt passes through an injection check
- Known injection patterns are detected: prompt overriding, role switching, delimiter injection, tool-call forgery
- Suspicious input is blocked or flagged, not silently passed through
- The check is applied at input ingestion time, not at LLM call time

---

### Guard 6: Audit Trail

**Severity:** Medium

**What it is:** Every LLM call, tool call, error, and safety decision must be recorded in structured form. `print()` statements are not an audit trail.

**Why:** When an agent fails in production — and it will — you need to reconstruct what happened. Which LLM call returned the unexpected response? Which tool failed and why? Was the circuit breaker triggered, or did the agent exit normally? Without structured audit records, debugging an agent failure is guesswork.

**Verification criteria:**
- LLM calls are logged with: timestamp, model, call duration, success/failure, error type if failed
- Tool calls are logged with: timestamp, tool name, call duration, success/failure, error type if failed
- Safety decisions (circuit breaker trips, approval denials, injection blocks) are logged
- Logs are structured (JSON or dataclass), not free-text `print()` output
- The audit record for a single agent invocation is retrievable as a unit

---

### Guard 7: Token Budget Control

**Severity:** Critical

**What it is:** Every agent invocation must have a maximum token consumption limit. When the cumulative token usage reaches the limit, the agent must stop — regardless of whether it has completed its task.

**Why:** An agent can be perfectly safe by Guards 1–6 and still burn money. No timeouts, no loops, no dangerous tools, clean audit trail — and a $47 API bill for a single conversation that should have cost $0.30. Guards 1 and 2 limit iterations; Guard 7 limits the resource cost of each iteration. They address different dimensions of the same problem.

**Verification criteria:**
- A token budget is set before each agent invocation
- Token usage across all LLM calls is accumulated within the invocation
- When cumulative usage exceeds the budget, the agent stops with a structured result
- The budget check occurs at `preflight` — before the next LLM or tool call, not after
- Token counting uses the same counting method as the model provider (token-based, not character-based where possible)

---

## Scope

### In Scope

These 7 guards cover **runtime safety** for agent execution:
- Execution containment (Guards 1–3, 7)
- Dangerous action control (Guard 4)
- Input sanitization (Guard 5)
- Observability (Guard 6)

### Out of Scope

- **Output content safety** — Use a moderation API. The spec does not cover whether the LLM's response contains harmful content.
- **Context window management** — Handled by model SDKs. The spec does not manage token limits within a single LLM call.
- **Rate limiting** — Infrastructure concern. The spec assumes the deployment environment handles API-level rate limits.
- **State rollback / transactions** — Application concern. The spec does not guarantee atomicity of multi-tool operations.
- **Parallel tool conflict detection** — Application concern. Whether two concurrent tool executions conflict depends on business logic.
- **Framework-specific configuration** — The spec defines *what* to guard, not *how* a given framework should implement it.

---

## Verification Methods

Compliance with this spec can be verified through multiple approaches. All are valid. None is exhaustive alone.

| Method | What it checks | Strengths | Limitations |
|--------|---------------|-----------|-------------|
| **LLM-assisted audit** | Semantic understanding of agent code against all 7 guards | Context-aware, explains findings, suggests fixes | Non-deterministic, requires LLM access |
| **Static analysis** | Pattern matching on source code (AST, regex) | Deterministic, fast, zero-cost, CI-compatible | Pattern-only, cannot judge intent |
| **Runtime library** | Guards enforced at execution time | Guaranteed enforcement, structured audit trail | Requires library integration |
| **Manual review** | Human inspection against the 7-guard checklist | Highest precision | Slow, inconsistent, doesn't scale |

The recommended combination: LLM-assisted audit during development, static analysis in CI, runtime library in production.

---

## Implementations

This spec is the authoritative definition. Implementations derive from it:

| Implementation | Type | Platform | Status |
|---------------|------|----------|--------|
| `SKILL.md` | LLM-assisted audit | Claude Code | Stable |
| `agent-fender` library | Runtime enforcement | Python 3.10+ | Stable |

Additional implementations (CLI scanner, Cursor rules, Copilot instructions, CI actions) are welcome as community contributions. Each should reference this spec as its source of truth.

---

## Versioning

This spec follows semantic versioning:

- **Major:** A guard is added, removed, or fundamentally redefined.
- **Minor:** Verification criteria are clarified or expanded.
- **Patch:** Wording improvements, examples added, typos fixed.

---

## License

This specification is licensed under MIT. Implementations may use any license.
