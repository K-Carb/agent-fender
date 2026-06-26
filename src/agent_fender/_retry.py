import asyncio
import logging
import random
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("agent_fender")


async def _execute_with_retry(
    call_fn: Callable[..., Any],
    *,
    max_retries: int = 0,
    base_delay_s: float = 1.0,
    is_retryable: Callable[[Any], bool],
    **kwargs: Any,
) -> Any:
    """Execute call_fn with exponential backoff + jitter. Retries only on retryable errors."""
    last_result = None
    for attempt in range(max_retries + 1):
        result = await call_fn(**kwargs)
        if result.success:
            return result
        if not is_retryable(result):
            return result
        last_result = result
        if attempt < max_retries:
            jitter = 0.75 + 0.5 * random.random()
            delay = base_delay_s * (2 ** attempt) * jitter
            logger.info("Retry %d/%d after %.2fs", attempt + 1, max_retries, delay)
            await asyncio.sleep(delay)
    return last_result
