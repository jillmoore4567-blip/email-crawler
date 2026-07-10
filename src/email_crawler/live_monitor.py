from __future__ import annotations

import asyncio
import json
from collections import deque
from pathlib import Path

from aiohttp import web


class LiveMonitorServer:
    def __init__(
        self,
        stream_path: str,
        output_dir: str,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        auth_token: str = "",
    ) -> None:
        self._stream_path = Path(stream_path)
        self._output_dir = Path(output_dir)
        self._host = host
        self._port = port
        self._auth_token = auth_token.strip()

        self._app = web.Application()
        self._app.add_routes(
            [
                web.get("/ws/live", self._handle_ws_live),
                web.get("/api/live/events", self._handle_api_events),
            ]
        )
        self._app.router.add_static("/", str(self._output_dir), show_index=True)

        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._tail_task: asyncio.Task[None] | None = None
        self._ws_clients: set[web.WebSocketResponse] = set()
        self._events: deque[dict] = deque(maxlen=3000)
        self._stream_offset = 0

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}"

    async def start(self) -> None:
        self._stream_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._stream_path.exists():
            self._stream_path.write_text("", encoding="utf-8")

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=self._host, port=self._port)
        await self._site.start()

        self._tail_task = asyncio.create_task(self._tail_loop())

    async def stop(self) -> None:
        if self._tail_task is not None:
            self._tail_task.cancel()
            try:
                await self._tail_task
            except asyncio.CancelledError:
                pass
            self._tail_task = None

        for ws in list(self._ws_clients):
            await ws.close()
        self._ws_clients.clear()

        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def _tail_loop(self) -> None:
        while True:
            await self._read_new_events()
            await asyncio.sleep(0.6)

    async def _read_new_events(self) -> None:
        try:
            with self._stream_path.open("r", encoding="utf-8") as handle:
                handle.seek(self._stream_offset)
                lines = handle.readlines()
                self._stream_offset = handle.tell()
        except OSError:
            return

        parsed: list[dict] = []
        for line in lines:
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                parsed.append(payload)
                self._events.append(payload)

        if not parsed:
            return

        message = json.dumps({"events": parsed}, separators=(",", ":"))
        stale: list[web.WebSocketResponse] = []
        for ws in self._ws_clients:
            if ws.closed:
                stale.append(ws)
                continue
            await ws.send_str(message)

        for ws in stale:
            self._ws_clients.discard(ws)

    async def _handle_ws_live(self, request: web.Request) -> web.StreamResponse:
        if not self._is_authorized(request):
            raise web.HTTPUnauthorized(text="unauthorized")

        ws = web.WebSocketResponse(heartbeat=25.0)
        await ws.prepare(request)

        self._ws_clients.add(ws)

        if self._events:
            await ws.send_json({"events": list(self._events)[-120:]})

        async for _msg in ws:
            # This socket is server-push only.
            pass

        self._ws_clients.discard(ws)
        return ws

    async def _handle_api_events(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            raise web.HTTPUnauthorized(text="unauthorized")

        since = request.query.get("since", "0")
        try:
            since_seq = int(since)
        except ValueError:
            since_seq = 0

        items = [
            item
            for item in self._events
            if int(item.get("sequence", 0) or 0) > since_seq
        ]
        return web.json_response({"events": items})

    def _is_authorized(self, request: web.Request) -> bool:
        if not self._auth_token:
            return True

        query_token = request.query.get("token", "")
        if query_token and query_token == self._auth_token:
            return True

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header.removeprefix("Bearer ").strip() == self._auth_token

        return False
