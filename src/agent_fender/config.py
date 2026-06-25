from dataclasses import dataclass, field


@dataclass
class GuardConfig:
    max_loop_count: int = 3
    max_tool_failures: int = 3
    dangerous_tools: frozenset[str] = field(default_factory=frozenset)
    llm_timeout_s: float = 60.0
    tool_timeout_s: float = 30.0
    circuit_breaker_reply: str = "Service is temporarily unavailable."
    llm_error_reply: str = "Service is temporarily unavailable."
