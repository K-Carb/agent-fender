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


async def safe_tool(
    tool_func: Callable[..., Any],
    *args: Any,
    timeout_s: float = 30.0,
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
                              user_message="Operation timed out.")
    except Exception as exc:
        logger.error("Tool execution error: %s", exc)
        return SafeToolResult(success=False, error_type="execution_error",
                              error_message=str(exc),
                              user_message="Operation failed.")
