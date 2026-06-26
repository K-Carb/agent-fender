import asyncio
import errno
import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("agent_fender")

_CONNECTION_EXCEPTIONS = (
    ConnectionError,
    ConnectionRefusedError,
    ConnectionResetError,
    ConnectionAbortedError,
    BrokenPipeError,
)


def _is_connection_error(exc: Exception) -> bool:
    if isinstance(exc, _CONNECTION_EXCEPTIONS):
        return True
    if isinstance(exc, OSError) and exc.errno in (
        errno.ECONNREFUSED, errno.ECONNRESET, errno.ECONNABORTED,
        errno.ENETDOWN, errno.ENETUNREACH, errno.ENETRESET,
        errno.EHOSTDOWN, errno.EHOSTUNREACH,
    ):
        return True
    cause = exc.__cause__
    while cause is not None:
        if isinstance(cause, _CONNECTION_EXCEPTIONS):
            return True
        if isinstance(cause, OSError) and cause.errno in (
            errno.ECONNREFUSED, errno.ECONNRESET, errno.ECONNABORTED,
        ):
            return True
        cause = cause.__cause__
    return False


@dataclass
class LLMResult:
    success: bool
    data: dict[str, Any] | None = None
    error_type: str | None = None        # "timeout" | "connection" | "response"
    error_message: str | None = None
    user_message: str | None = None

    @property
    def is_retryable(self) -> bool:
        return self.error_type in ("timeout", "connection")


async def _call_llm_once(
    llm_call: Callable[..., Any],
    timeout_s: float,
    fallback_message: str,
    **kwargs: Any,
) -> LLMResult:
    if inspect.iscoroutinefunction(llm_call):
        coro = llm_call(**kwargs)
    else:
        coro = asyncio.to_thread(llm_call, **kwargs)
    try:
        result = await asyncio.wait_for(coro, timeout=timeout_s)
        return LLMResult(success=True, data=result)
    except TimeoutError:
        logger.warning("LLM timeout after %.1fs", timeout_s)
        return LLMResult(success=False, error_type="timeout", user_message=fallback_message)
    except Exception as exc:
        if _is_connection_error(exc):
            logger.error("LLM connection error: %s", exc)
            return LLMResult(success=False, error_type="connection",
                             error_message=str(exc), user_message=fallback_message)
        logger.error("LLM response error: %s", exc)
        return LLMResult(success=False, error_type="response",
                         error_message=str(exc), user_message=fallback_message)


async def safe_llm_chat(
    llm_call: Callable[..., Any],
    *,
    timeout_s: float = 60.0,
    fallback_message: str = "Service is temporarily unavailable.",
    retries: int = 0,
    retry_base_delay_s: float = 1.0,
    **kwargs: Any,
) -> LLMResult:
    """Wrap an LLM chat call with timeout, error classification, and optional retry.

    Handles both sync and async callables. Errors are classified as
    timeout, connection, or response. Retries only on retryable errors
    (timeout and connection) with exponential backoff + jitter.
    """
    if retries <= 0:
        return await _call_llm_once(llm_call, timeout_s=timeout_s,
                                     fallback_message=fallback_message, **kwargs)

    from agent_fender._retry import _execute_with_retry
    return await _execute_with_retry(
        _call_llm_once,
        max_retries=retries,
        base_delay_s=retry_base_delay_s,
        is_retryable=lambda r: r.is_retryable,
        llm_call=llm_call,
        timeout_s=timeout_s,
        fallback_message=fallback_message,
        **kwargs,
    )


async def safe_embed(
    embed_call: Callable[..., Any],
    *,
    timeout_s: float = 30.0,
    fallback_message: str = "Embedding failed.",
    **kwargs: Any,
) -> LLMResult:
    """Wrap an embedding call with timeout and error classification."""
    if inspect.iscoroutinefunction(embed_call):
        coro = embed_call(**kwargs)
    else:
        coro = asyncio.to_thread(embed_call, **kwargs)
    try:
        result = await asyncio.wait_for(coro, timeout=timeout_s)
        return LLMResult(success=True, data=result)
    except TimeoutError:
        logger.warning("Embedding timeout after %.1fs", timeout_s)
        return LLMResult(success=False, error_type="timeout",
                         user_message=fallback_message)
    except Exception as exc:
        if _is_connection_error(exc):
            logger.error("Embedding connection error: %s", exc)
            return LLMResult(success=False, error_type="connection",
                             error_message=str(exc),
                             user_message=fallback_message)
        logger.error("Embedding error: %s", exc)
        return LLMResult(success=False, error_type="response",
                         error_message=str(exc),
                         user_message=fallback_message)
