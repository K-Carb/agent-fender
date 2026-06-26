from dataclasses import dataclass, field


@dataclass
class FenderConfig:
    """Configuration for all 6 agent safety guards.

    Args:
        max_loop_count: Max agent loop iterations before circuit breaker trips.
        max_tool_failures: Max cumulative tool failures before circuit breaker trips.
        dangerous_tools: Tool names that require human approval before execution.
        llm_timeout_s: Per-LLM-call timeout in seconds.
        tool_timeout_s: Per-tool-call timeout in seconds.
        circuit_breaker_reply: Fallback message when circuit breaker trips.
        llm_error_reply: Fallback message when LLM call fails.
        tool_error_reply: Fallback message when tool call fails.
        llm_retries: Max retry attempts for LLM calls (0 = no retry).
        tool_retries: Max retry attempts for tool calls (0 = no retry).
        retry_base_delay_s: Base delay in seconds between retries (doubles each attempt).
    """

    max_loop_count: int = 3
    max_tool_failures: int = 3
    dangerous_tools: frozenset[str] = field(default_factory=frozenset)
    llm_timeout_s: float = 60.0
    tool_timeout_s: float = 30.0
    circuit_breaker_reply: str = "Service is temporarily unavailable."
    llm_error_reply: str = "Service is temporarily unavailable."
    tool_error_reply: str = "Operation failed."
    llm_retries: int = 0
    tool_retries: int = 0
    retry_base_delay_s: float = 1.0

    def __post_init__(self):
        if self.max_loop_count < 1:
            raise ValueError(f"max_loop_count must be >= 1, got {self.max_loop_count}")
        if self.max_tool_failures < 1:
            raise ValueError(f"max_tool_failures must be >= 1, got {self.max_tool_failures}")
        if self.llm_timeout_s <= 0:
            raise ValueError(f"llm_timeout_s must be > 0, got {self.llm_timeout_s}")
        if self.tool_timeout_s <= 0:
            raise ValueError(f"tool_timeout_s must be > 0, got {self.tool_timeout_s}")
        if self.llm_retries < 0:
            raise ValueError(f"llm_retries must be >= 0, got {self.llm_retries}")
        if self.tool_retries < 0:
            raise ValueError(f"tool_retries must be >= 0, got {self.tool_retries}")
        if self.retry_base_delay_s <= 0:
            raise ValueError(f"retry_base_delay_s must be > 0, got {self.retry_base_delay_s}")
