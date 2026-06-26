import asyncio
import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("agent_fender")


@dataclass
class SafeToolResult:
    success: bool
    data: Any = None                     # tool return value, not forced to str
    error_type: str | None = None        # "timeout" | "execution_error"
    error_message: str | None = None
    user_message: str | None = None

    @property
    def is_retryable(self) -> bool:
        return self.error_type in ("timeout",)


async def _call_tool_once(
    tool_func: Callable[..., Any],
    *args: Any,
    timeout_s: float,
    fallback_message: str,
    **kwargs: Any,
) -> SafeToolResult:
    if inspect.iscoroutinefunction(tool_func):
        coro = tool_func(*args, **kwargs)
    else:
        coro = asyncio.to_thread(tool_func, *args, **kwargs)
    try:
        result = await asyncio.wait_for(coro, timeout=timeout_s)
        return SafeToolResult(success=True, data=result)
    except TimeoutError:
        logger.warning("Tool timeout after %.1fs", timeout_s)
        return SafeToolResult(success=False, error_type="timeout",
                              user_message=fallback_message)
    except Exception as exc:
        logger.error("Tool execution error: %s", exc)
        return SafeToolResult(success=False, error_type="execution_error",
                              error_message=str(exc),
                              user_message=fallback_message)


async def safe_tool(
    tool_func: Callable[..., Any],
    *args: Any,
    timeout_s: float = 30.0,
    fallback_message: str = "Operation failed.",
    retries: int = 0,
    retry_base_delay_s: float = 1.0,
    **kwargs: Any,
) -> SafeToolResult:
    """Wrap a tool execution with timeout, error classification, and optional retry.

    Handles both sync and async tool functions. Errors are classified as
    timeout or execution_error. Retries on timeout with exponential backoff + jitter.
    """
    if retries <= 0:
        return await _call_tool_once(tool_func, *args, timeout_s=timeout_s,
                                      fallback_message=fallback_message, **kwargs)

    from agent_fender._retry import _execute_with_retry

    async def _call_with_args(**kw: Any) -> SafeToolResult:
        return await _call_tool_once(tool_func, *args, timeout_s=timeout_s,
                                      fallback_message=fallback_message, **kw)

    return await _execute_with_retry(
        _call_with_args,
        max_retries=retries,
        base_delay_s=retry_base_delay_s,
        is_retryable=lambda r: r.is_retryable,
        **kwargs,
    )
