from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from agent_fender.config import FenderConfig

logger = logging.getLogger("agent_fender")


@dataclass
class CircuitBreakerResult:
    should_break: bool
    reason: str | None = None            # "max_loops" | "max_tool_failures" | "repeated_action" | "action_loop" | "token_budget"
    fallback_reply: str | None = None


def check_action_loop(
    action_history: Sequence[str],
    *,
    max_repeated_actions: int = 3,
    max_action_sequence_repeats: int = 2,
) -> CircuitBreakerResult | None:
    """Detect repeated-action loops from tool call history. Pure function.

    Returns CircuitBreakerResult if a loop is detected, None otherwise.
    Two detection strategies:
      1. Same-action streak: same action N+ times in a row
      2. A,B,A,B cycle: any 2-action pattern repeated N+ times
    """
    if not action_history:
        return None

    # Strategy 1: same-action streak
    if max_repeated_actions > 0 and len(action_history) >= max_repeated_actions:
        recent = list(action_history)[-max_repeated_actions:]
        if len(set(recent)) == 1:
            logger.warning("Circuit breaker: repeated_action (%r x%d)",
                           recent[0], max_repeated_actions)
            return CircuitBreakerResult(
                should_break=True,
                reason="repeated_action",
                fallback_reply=None,
            )

    # Strategy 2: A,B two-action cycle
    if max_action_sequence_repeats > 0 and len(action_history) >= 4:
        # Look at the last 2 actions; if they form a pattern A,B,A,B, break
        a = action_history[-4]
        b = action_history[-3]
        if a != b and action_history[-2] == a and action_history[-1] == b:
            # Count consecutive A,B pairs scanning from the end
            pattern_count = 0
            pos = len(action_history)
            while pos >= 2:
                if action_history[pos - 2] == a and action_history[pos - 1] == b:
                    pattern_count += 1
                    pos -= 2
                else:
                    break
            if pattern_count >= max_action_sequence_repeats:
                logger.warning("Circuit breaker: action_loop (%r,%r x%d)",
                               a, b, pattern_count)
                return CircuitBreakerResult(
                    should_break=True,
                    reason="action_loop",
                    fallback_reply=None,
                )

    return None


class CircuitBreaker:
    """Checks loop_count, tool_failures, action_history, and tokens_used against configured thresholds."""

    def __init__(self, config: FenderConfig):
        self.config = config

    def check(
        self,
        *,
        loop_count: int,
        tool_failures: int,
        action_history: Sequence[str] | None = None,
        tokens_used: int = 0,
    ) -> CircuitBreakerResult:
        """Return whether the circuit should break based on current counts and action history."""
        if action_history:
            loop_result = check_action_loop(
                action_history,
                max_repeated_actions=self.config.max_repeated_actions,
                max_action_sequence_repeats=self.config.max_action_sequence_repeats,
            )
            if loop_result is not None:
                loop_result.fallback_reply = self.config.circuit_breaker_reply
                return loop_result

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
        if self.config.token_budget > 0 and tokens_used >= self.config.token_budget:
            logger.warning("Circuit breaker: token_budget (%d >= %d)",
                           tokens_used, self.config.token_budget)
            return CircuitBreakerResult(
                should_break=True,
                reason="token_budget",
                fallback_reply=self.config.circuit_breaker_reply,
            )
        return CircuitBreakerResult(should_break=False)
