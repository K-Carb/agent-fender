# Changelog

## [0.2.0] — 2026-06-29

### Added
- Guard 7: Token Budget Control — 7/7 guards complete
- `FenderConfig.token_budget` (default 0 = disabled, backward compatible)
- `FenderConfig.token_counter` — custom token counting callback (None = `len(text)//4` approximation)
- `AgentFender.count_tokens(text)` — token counting with configurable counter
- `CircuitBreaker.check()` and `AgentFender.preflight()` now accept `tokens_used` parameter
- `CircuitBreakerResult.reason="token_budget"` for budget-exceeded trips
- `FenderSession.token_budget_trips` counter
- Guard 7 inline pattern in `references/inline-patterns.md`
- Token budget integration guide in `references/library-integration.md`

### Changed
- README: 7/7 guard coverage, comparison table updated, Quick Start includes token budget
- `docs/failure-modes.md`: failure mode #3 updated with actual usage
- `SKILL.md`: Guard 7 status changed from "pending" to stable
- 124 tests (18 new for token budget)

## [0.1.0] — 2026-06-26

### Added
- Initial release
- 6 guard components: circuit breaker, safe LLM, safe tool, dangerous tool gating, injection detection, dedup
- `AgentFender` facade with 4-step API
- `FenderSession` audit trail
- Claude Code SKILL.md for agent code auditing
- Connection error detection via instance-checking (not string-matching)
- Pre-compiled regex for injection detection
- Input length cap (4096 chars) for injection scanning
- `safe_embed` for embedding calls
- `needs_deeper_scan` property on `InjectionCheck`
- `fallback_message` parameter on `safe_tool`
- `tool_error_reply` config field
- Config validation via `__post_init__`
- 106 tests, zero dependencies
