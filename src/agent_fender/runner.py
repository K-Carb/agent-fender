import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from agent_fender.approval import (
    ApprovalCheck,
    DedupCheck,
    InjectionCheck,
    check_dangerous,
    check_dedup,
    check_injection,
)
from agent_fender.circuit_breaker import CircuitBreaker, CircuitBreakerResult
from agent_fender.config import GuardConfig
from agent_fender.safe_llm import LLMResult, safe_llm_chat
from agent_fender.safe_tool import SafeToolResult, safe_tool

logger = logging.getLogger("agent_fender")


@dataclass
class GuardSession:
    """Audit trail for one agent invocation. Tracks what happened."""

    llm_calls: int = 0
    llm_timeouts: int = 0
    llm_connection_errors: int = 0
    llm_response_errors: int = 0
    tool_calls: int = 0
    tool_timeouts: int = 0
    tool_execution_errors: int = 0
    circuit_breaker_trips: int = 0
    circuit_breaker_reason: str | None = None
    approval_checks: int = 0
    approvals_required: int = 0
    injection_checks: int = 0
    injection_blocks: int = 0
    dedup_checks: int = 0
    dedup_hits: int = 0
    started_at: float = 0.0

    @property
    def total_errors(self) -> int:
        return (
            self.llm_timeouts + self.llm_connection_errors + self.llm_response_errors
            + self.tool_timeouts + self.tool_execution_errors
        )

    @property
    def elapsed_s(self) -> float:
        return time.time() - self.started_at if self.started_at else 0.0

    @property
    def summary(self) -> str:
        lines = [
            f"GuardSession ({self.elapsed_s:.1f}s):",
            f"  LLM: {self.llm_calls} calls"
            + (f" ({self.llm_timeouts} timeout, {self.llm_connection_errors} connection, {self.llm_response_errors} response)" if self.total_errors else " (all ok)"),  # noqa: E501
            f"  Tools: {self.tool_calls} calls"
            + (f" ({self.tool_timeouts} timeout, {self.tool_execution_errors} error)" if (self.tool_timeouts + self.tool_execution_errors) else " (all ok)"),  # noqa: E501
            f"  Circuit breaker: {'tripped' if self.circuit_breaker_trips else 'ok'}"
            + (f" ({self.circuit_breaker_reason})" if self.circuit_breaker_reason else ""),  # noqa: E501
            f"  Approval: {self.approval_checks} checks, {self.approvals_required} required",
            f"  Injection: {self.injection_checks} checks, {self.injection_blocks} blocks",
            f"  Dedup: {self.dedup_checks} checks, {self.dedup_hits} hits",
        ]
        if self.total_errors:
            lines.append(f"  TOTAL ERRORS: {self.total_errors}")
        return "\n".join(lines)


class AgentGuard:
    def __init__(self, config: GuardConfig):
        self.config = config
        self._breaker = CircuitBreaker(config)
        self._session: GuardSession | None = None

    # ── session management ──────────────────────────

    def start_session(self) -> GuardSession:
        self._session = GuardSession(started_at=time.time())
        return self._session

    def stop_session(self) -> GuardSession | None:
        s = self._session
        self._session = None
        return s

    @property
    def session(self) -> GuardSession | None:
        return self._session

    # ── guard methods ───────────────────────────────

    def preflight(self, *, loop_count: int, tool_failures: int) -> CircuitBreakerResult:
        result = self._breaker.check(loop_count=loop_count, tool_failures=tool_failures)
        if result.should_break and self._session:
            self._session.circuit_breaker_trips += 1
            self._session.circuit_breaker_reason = result.reason
        return result

    async def safe_llm(
        self, llm_call: Callable[..., Any], *, timeout_s: float | None = None, **kwargs: Any
    ) -> LLMResult:
        ts = timeout_s if timeout_s is not None else self.config.llm_timeout_s
        result = await safe_llm_chat(llm_call, timeout_s=ts,
                                     fallback_message=self.config.llm_error_reply, **kwargs)
        if self._session:
            self._session.llm_calls += 1
            if not result.success:
                if result.error_type == "timeout":
                    self._session.llm_timeouts += 1
                elif result.error_type == "connection":
                    self._session.llm_connection_errors += 1
                else:
                    self._session.llm_response_errors += 1
        return result

    def check_tools(self, tool_names: list[str]) -> ApprovalCheck:
        result = check_dangerous(tool_names, self.config.dangerous_tools)
        if self._session:
            self._session.approval_checks += 1
            if result.requires_approval:
                self._session.approvals_required += 1
        return result

    async def safe_tool(
        self, tool_func: Callable[..., Any], *args: Any,
        timeout_s: float | None = None, **kwargs: Any,
    ) -> SafeToolResult:
        ts = timeout_s if timeout_s is not None else self.config.tool_timeout_s
        result = await safe_tool(tool_func, *args, timeout_s=ts, **kwargs)
        if self._session:
            self._session.tool_calls += 1
            if not result.success:
                if result.error_type == "timeout":
                    self._session.tool_timeouts += 1
                else:
                    self._session.tool_execution_errors += 1
        return result

    def check_injection(self, text: str) -> InjectionCheck:
        result = check_injection(text)
        if self._session:
            self._session.injection_checks += 1
            if result.is_suspicious:
                self._session.injection_blocks += 1
        return result

    def check_dedup(self, key: str, seen_keys: set[str]) -> DedupCheck:
        result = check_dedup(key, seen_keys)
        if self._session:
            self._session.dedup_checks += 1
            if result.is_duplicate:
                self._session.dedup_hits += 1
        return result
