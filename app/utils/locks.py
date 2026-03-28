from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable


class AsyncSingleFlightRunner:
    """Coalesces concurrent rebuild requests into a single sequential loop."""

    def __init__(
        self,
        callback: Callable[[str], Awaitable[None]],
        *,
        logger: logging.Logger | None = None,
        debounce_seconds: float = 0.0,
    ) -> None:
        self._callback = callback
        self._logger = logger or logging.getLogger(__name__)
        self._debounce_seconds = debounce_seconds
        self._execution_lock = asyncio.Lock()
        self._pending = False
        self._reasons: set[str] = set()
        self._task: asyncio.Task[None] | None = None

    async def request(self, reason: str) -> None:
        self._pending = True
        self._reasons.add(reason)
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._drain())

    async def wait(self) -> None:
        if self._task is not None:
            await self._task

    async def _drain(self) -> None:
        while self._pending:
            if self._debounce_seconds > 0:
                await asyncio.sleep(self._debounce_seconds)
            self._pending = False
            reasons = sorted(self._reasons)
            self._reasons.clear()
            reason_text = ", ".join(reasons) if reasons else "unspecified"
            async with self._execution_lock:
                self._logger.info("Starting single-flight rebuild: %s", reason_text)
                try:
                    await self._callback(reason_text)
                except Exception:  # pragma: no cover - log path
                    self._logger.exception("Rebuild callback failed")
