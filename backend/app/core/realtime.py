"""Real-time hub: WebSocket fan-out by channel.

Channels used by the app:
  list:<list_id>        collaborative shopping list changes
  store:<store_id>      inventory changes, restock alerts, gate events (staff dashboards)
  user:<user_id>        personal notifications (task assigned, order ready, credentials...)
  admin                 platform-wide events (new credential requests, support tickets)

Route handlers are synchronous (run in a threadpool), so `publish()` is thread-safe and
schedules the async send onto the server's event loop.
"""
import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime

from fastapi import WebSocket

log = logging.getLogger("realtime")


def _default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    return str(o)


class RealtimeHub:
    def __init__(self) -> None:
        self.channels: dict[str, set[WebSocket]] = defaultdict(set)
        self.loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    async def connect(self, ws: WebSocket, channels: list[str]) -> None:
        await ws.accept()
        for ch in channels:
            self.channels[ch].add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        for subs in self.channels.values():
            subs.discard(ws)

    async def _send(self, channel: str, message: str) -> None:
        dead = []
        for ws in list(self.channels.get(channel, ())):
            try:
                await ws.send_text(message)
            except Exception:  # client went away
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def publish(self, channel: str, event: str, data: dict | None = None) -> None:
        message = json.dumps({"channel": channel, "event": event, "data": data or {}}, default=_default)
        if self.loop is None or self.loop.is_closed():
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self.loop:
            self.loop.create_task(self._send(channel, message))
        else:
            asyncio.run_coroutine_threadsafe(self._send(channel, message), self.loop)


hub = RealtimeHub()
