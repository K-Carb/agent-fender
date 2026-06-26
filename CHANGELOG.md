# Changelog

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
- 75 tests, zero dependencies
