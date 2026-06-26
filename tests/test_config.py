import pytest
from agent_fender.config import FenderConfig


class TestFenderConfigValidation:
    def test_defaults_are_valid(self):
        config = FenderConfig()
        assert config.max_loop_count == 3
        assert config.llm_timeout_s == 60.0

    def test_negative_max_loop_count_raises(self):
        with pytest.raises(ValueError, match="max_loop_count"):
            FenderConfig(max_loop_count=-1)

    def test_zero_max_loop_count_raises(self):
        with pytest.raises(ValueError, match="max_loop_count"):
            FenderConfig(max_loop_count=0)

    def test_negative_max_tool_failures_raises(self):
        with pytest.raises(ValueError, match="max_tool_failures"):
            FenderConfig(max_tool_failures=-1)

    def test_negative_llm_timeout_raises(self):
        with pytest.raises(ValueError, match="llm_timeout_s"):
            FenderConfig(llm_timeout_s=-5.0)

    def test_zero_llm_timeout_raises(self):
        with pytest.raises(ValueError, match="llm_timeout_s"):
            FenderConfig(llm_timeout_s=0.0)

    def test_negative_tool_timeout_raises(self):
        with pytest.raises(ValueError, match="tool_timeout_s"):
            FenderConfig(tool_timeout_s=-1.0)

    def test_zero_tool_timeout_raises(self):
        with pytest.raises(ValueError, match="tool_timeout_s"):
            FenderConfig(tool_timeout_s=0.0)

    def test_empty_dangerous_tools_is_ok(self):
        config = FenderConfig(dangerous_tools=frozenset())
        assert config.dangerous_tools == frozenset()

    def test_empty_reply_strings_are_ok(self):
        config = FenderConfig(circuit_breaker_reply="", llm_error_reply="")
        assert config.circuit_breaker_reply == ""

    def test_retry_defaults(self):
        config = FenderConfig()
        assert config.llm_retries == 0
        assert config.tool_retries == 0
        assert config.retry_base_delay_s == 1.0

    def test_negative_llm_retries_raises(self):
        with pytest.raises(ValueError, match="llm_retries"):
            FenderConfig(llm_retries=-1)

    def test_negative_tool_retries_raises(self):
        with pytest.raises(ValueError, match="tool_retries"):
            FenderConfig(tool_retries=-1)

    def test_zero_retry_delay_raises(self):
        with pytest.raises(ValueError, match="retry_base_delay_s"):
            FenderConfig(retry_base_delay_s=0.0)
