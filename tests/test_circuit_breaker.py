from agent_fender.circuit_breaker import CircuitBreaker, CircuitBreakerResult


class TestCircuitBreakerResult:
    def test_should_break_false_when_under_limit(self):
        result = CircuitBreakerResult(should_break=False)
        assert result.should_break is False
        assert result.reason is None
        assert result.fallback_reply is None

    def test_should_break_true_with_reason(self):
        result = CircuitBreakerResult(should_break=True, reason="max_loops",
                                      fallback_reply="Service temporarily unavailable")
        assert result.should_break is True
        assert result.reason == "max_loops"
        assert result.fallback_reply == "Service temporarily unavailable"


class TestCircuitBreaker:
    def test_normal_operation(self, config):
        cb = CircuitBreaker(config)
        result = cb.check(loop_count=1, tool_failures=0)
        assert result.should_break is False

    def test_loop_count_exceeded(self, config):
        cb = CircuitBreaker(config)
        result = cb.check(loop_count=3, tool_failures=0)
        assert result.should_break is True
        assert result.reason == "max_loops"
        assert result.fallback_reply is not None

    def test_tool_failures_exceeded(self, config):
        cb = CircuitBreaker(config)
        result = cb.check(loop_count=1, tool_failures=3)
        assert result.should_break is True
        assert result.reason == "max_tool_failures"

    def test_loop_count_checked_first(self, config):
        """When both loop_count and tool_failures exceed limits, report max_loops first."""
        cb = CircuitBreaker(config)
        result = cb.check(loop_count=5, tool_failures=5)
        assert result.should_break is True
        assert result.reason == "max_loops"

    def test_both_under_limit(self, config):
        cb = CircuitBreaker(config)
        result = cb.check(loop_count=2, tool_failures=2)
        assert result.should_break is False

    def test_uses_config_thresholds(self):
        from agent_fender.config import FenderConfig
        config = FenderConfig(max_loop_count=5, max_tool_failures=5)
        cb = CircuitBreaker(config)
        assert cb.check(loop_count=4, tool_failures=4).should_break is False
        assert cb.check(loop_count=5, tool_failures=0).should_break is True
