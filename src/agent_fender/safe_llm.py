import asyncio
import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("agent_fender")


@dataclass
class LLMResult:
    success: bool
    data: dict[str, Any] | None = None
    error_type: str | None = None        # "timeout" | "connection" | "response"
    error_message: str | None = None
    user_message: str | None = None

    @property
    def is_retryable(self) -> bool:
        return self.error_type in ("timeout",)


async def safe_llm_chat(
    llm_call: Callable[..., Any],
    *,
    timeout_s: float = 60.0,
    fallback_message: str = "Service is temporarily unavailable.",
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
        if "Connect" in type(exc).__name__:
            logger.error("LLM connection error: %s", exc)
            return LLMResult(success=False, error_type="connection",
                             error_message=str(exc), user_message=fallback_message)
        logger.error("LLM response error: %s", exc)
        return LLMResult(success=False, error_type="response",
                         error_message=str(exc), user_message=fallback_message)


async def safe_embed(
    embed_call: Callable[..., Any],
    *,
    timeout_s: float = 30.0,
    **kwargs: Any,
) -> LLMResult:
    """Same pattern as safe_llm_chat, for embedding calls."""
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
                         user_message="Embedding timed out.")
    except Exception as exc:
        logger.error("Embedding error: %s", exc)
        return LLMResult(success=False, error_type="response",
                         error_message=str(exc),
                         user_message="Embedding failed.")
