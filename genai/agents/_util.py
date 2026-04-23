from __future__ import annotations

import functools
import logging
from typing import Any, Awaitable, Callable

from state import Event, GraphState

log = logging.getLogger("vidnots.agents")


async def emit(state: GraphState, event_type: str, **data: Any) -> None:
    q = state.get("events")
    if q is None:
        return
    await q.put(Event(type=event_type, data=data))  # type: ignore[arg-type]


def resilient(agent_name: str, fallback: dict):
    """Wrap an agent node so any exception is reported as a progress/error
    event and the node returns `fallback` state instead of crashing the graph.

    One agent failing (e.g. Transcriber hits YouTube anti-bot) must never
    prevent the Synthesizer from running on whatever the others produced.
    """

    def _wrap(fn: Callable[[GraphState], Awaitable[dict]]):
        @functools.wraps(fn)
        async def _inner(state: GraphState) -> dict:
            try:
                return await fn(state)
            except Exception as exc:
                log.exception("agent %s failed", agent_name)
                await emit(
                    state,
                    "progress",
                    agent=agent_name,
                    status="error",
                    message=f"{type(exc).__name__}: {exc}",
                )
                return fallback

        return _inner

    return _wrap
