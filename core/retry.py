import asyncio
import logging
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")
log = logging.getLogger(__name__)


class TransientError(Exception):
    pass


class PermanentError(Exception):
    pass


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    delays: list[int],
    is_transient: Callable[[BaseException], bool],
    context: str = "",
) -> T:
    attempts = 1 + len(delays)
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except BaseException as exc:
            last_exc = exc
            if not is_transient(exc):
                raise
            if attempt == attempts:
                break
            delay = delays[attempt - 1]
            log.warning(
                "retry %s attempt=%d/%d delay=%ds err=%r",
                context, attempt, attempts, delay, exc,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc
