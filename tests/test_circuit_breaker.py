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


class TestCheckActionLoop:
    def test_no_break_on_empty_history(self):
        from agent_fender.circuit_breaker import check_action_loop
        result = check_action_loop([])
        assert result is None

    def test_no_break_on_single_action(self):
        from agent_fender.circuit_breaker import check_action_loop
        result = check_action_loop(["search_files"])
        assert result is None

    def test_no_break_on_two_same_actions(self):
        from agent_fender.circuit_breaker import check_action_loop
        result = check_action_loop(["search_files", "search_files"])
        assert result is None

    def test_break_on_three_same_actions(self):
        from agent_fender.circuit_breaker import check_action_loop
        result = check_action_loop(["search_files", "search_files", "search_files"])
        assert result is not None
        assert result.should_break is True
        assert result.reason == "repeated_action"

    def test_break_on_five_same_actions(self):
        from agent_fender.circuit_breaker import check_action_loop
        history = ["search_files"] * 5
        result = check_action_loop(history)
        assert result is not None
        assert result.reason == "repeated_action"

    def test_no_break_on_interleaved_different_actions(self):
        from agent_fender.circuit_breaker import check_action_loop
        result = check_action_loop(["search_files", "get_metrics", "search_files"])
        assert result is None

    def test_break_on_abab_cycle(self):
        from agent_fender.circuit_breaker import check_action_loop
        result = check_action_loop(["search_files", "get_metrics", "search_files", "get_metrics"])
        assert result is not None
        assert result.should_break is True
        assert result.reason == "action_loop"

    def test_no_break_on_aba_only(self):
        """A,B,A is only 1 full cycle, not 2 — should not break."""
        from agent_fender.circuit_breaker import check_action_loop
        result = check_action_loop(["search_files", "get_metrics", "search_files"])
        assert result is None

    def test_custom_thresholds(self):
        from agent_fender.circuit_breaker import check_action_loop
        result = check_action_loop(
            ["a", "a"], max_repeated_actions=2, max_action_sequence_repeats=2,
        )
        assert result is not None
        assert result.reason == "repeated_action"

    def test_disabled_repeated_actions(self):
        from agent_fender.circuit_breaker import check_action_loop
        result = check_action_loop(
            ["x", "x", "x"], max_repeated_actions=0, max_action_sequence_repeats=2,
        )
        assert result is None

    def test_disabled_sequence_repeats(self):
        from agent_fender.circuit_breaker import check_action_loop
        result = check_action_loop(
            ["a", "b", "a", "b"], max_repeated_actions=3, max_action_sequence_repeats=0,
        )
        assert result is None

    def test_ab_pattern_counted_correctly(self):
        """A,B,A,B,A,B = 3 cycles of A,B → should break at default threshold 2."""
        from agent_fender.circuit_breaker import check_action_loop
        result = check_action_loop(["a", "b", "a", "b", "a", "b"])
        assert result is not None
        assert result.reason == "action_loop"


class TestCircuitBreakerWithActionHistory:
    def test_action_loop_via_circuit_breaker(self, config):
        cb = CircuitBreaker(config)
        result = cb.check(loop_count=1, tool_failures=0,
                          action_history=["x", "x", "x"])
        assert result.should_break is True
        assert result.reason == "repeated_action"
        assert result.fallback_reply == config.circuit_breaker_reply

    def test_no_action_history_no_loop_check(self, config):
        cb = CircuitBreaker(config)
        result = cb.check(loop_count=1, tool_failures=0)
        assert result.should_break is False

    def test_loop_count_still_checked_after_action_check(self, config):
        """If action_history is clean, loop_count/tool_failures still apply."""
        cb = CircuitBreaker(config)
        result = cb.check(loop_count=3, tool_failures=0,
                          action_history=["search_files", "get_metrics"])
        assert result.should_break is True
        assert result.reason == "max_loops"


class TestCircuitBreakerTokenBudget:
    def test_token_budget_disabled_when_zero(self, config):
        """token_budget=0 means disabled — never trips."""
        cb = CircuitBreaker(config)
        result = cb.check(loop_count=1, tool_failures=0, tokens_used=999_999)
        assert result.should_break is False

    def test_token_budget_trips_when_exceeded(self, config):
        config.token_budget = 100_000
        cb = CircuitBreaker(config)
        result = cb.check(loop_count=1, tool_failures=0, tokens_used=100_000)
        assert result.should_break is True
        assert result.reason == "token_budget"
        assert result.fallback_reply == config.circuit_breaker_reply

    def test_token_budget_not_tripped_when_under(self, config):
        config.token_budget = 100_000
        cb = CircuitBreaker(config)
        result = cb.check(loop_count=1, tool_failures=0, tokens_used=50_000)
        assert result.should_break is False

    def test_token_budget_checked_after_loop_count(self, config):
        """When both exceed limits, max_loops wins (checked first)."""
        config.token_budget = 100_000
        cb = CircuitBreaker(config)
        result = cb.check(loop_count=5, tool_failures=0, tokens_used=999_999)
        assert result.should_break is True
        assert result.reason == "max_loops"

    def test_token_budget_exact_boundary(self, config):
        """tokens_used == budget trips (>= check)."""
        config.token_budget = 1000
        cb = CircuitBreaker(config)
        result = cb.check(loop_count=1, tool_failures=0, tokens_used=1000)
        assert result.should_break is True
        assert result.reason == "token_budget"

    def test_token_budget_zero_tokens_used(self, config):
        """tokens_used=0, budget>0 → normal operation."""
        config.token_budget = 100_000
        cb = CircuitBreaker(config)
        result = cb.check(loop_count=1, tool_failures=0, tokens_used=0)
        assert result.should_break is False

    def test_token_budget_checked_last(self, config):
        """action_loop + loop_count + tool_failures + token_budget all exceed:
        action_loop triggers first since it has the highest-priority check order."""
        config.token_budget = 100_000
        cb = CircuitBreaker(config)
        result = cb.check(
            loop_count=5, tool_failures=5, tokens_used=999_999,
            action_history=["x", "x", "x"],
        )
        assert result.should_break is True
        assert result.reason == "repeated_action"
