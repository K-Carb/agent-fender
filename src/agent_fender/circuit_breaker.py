import logging
from dataclasses import dataclass

from agent_fender.config import GuardConfig

logger = logging.getLogger("agent_fender")


@dataclass
class CircuitBreakerResult:
    should_break: bool
    reason: str | None = None            # "max_loops" | "max_tool_failures"
    fallback_reply: str | None = None


class CircuitBreaker:
    def __init__(self, config: GuardConfig):
        self.config = config

    def check(self, *, loop_count: int, tool_failures: int) -> CircuitBreakerResult:
        if loop_count >= self.config.max_loop_count:
            logger.warning("Circuit breaker: max_loops (%d >= %d)",
                           loop_count, self.config.max_loop_count)
            return CircuitBreakerResult(
                should_break=True,
                reason="max_loops",
                fallback_reply=self.config.circuit_breaker_reply,
            )
        if tool_failures >= self.config.max_tool_failures:
            logger.warning("Circuit breaker: max_tool_failures (%d >= %d)",
                           tool_failures, self.config.max_tool_failures)
            return CircuitBreakerResult(
                should_break=True,
                reason="max_tool_failures",
                fallback_reply=self.config.circuit_breaker_reply,
            )
        return CircuitBreakerResult(should_break=False)
