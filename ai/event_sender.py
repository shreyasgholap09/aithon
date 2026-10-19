"""
Event Sender & Optimized WebSocket Bridge Module
Separates high-priority safety telemetry from high-bandwidth video frame streams.
Features:
- Non-blocking async video dispatch with backpressure frame-dropping for slow consumers.
- Zero-drop priority delivery for safety alerts and risk violations.
- Direct measurement of network serialization and transmission latency.
"""

import asyncio
import json
import logging
import time
from typing import Set, Dict, Any, Callable, Optional
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EventSender")

class EventSender:
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.connected_clients: Set[websockets.WebSocketServerProtocol] = set()
        self.on_command_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
        self.on_connect_callback: Optional[Callable[[], Optional[Dict[str, Any]]]] = None
        self._server = None
        
        # Backpressure guard: tracks pending video transmissions per client
        self._pending_video_tasks: Dict[Any, asyncio.Task] = {}
        self.last_tx_ms: float = 0.0

    async def register(self, websocket):
        self.connected_clients.add(websocket)
        logger.info(f"Frontend client connected from {websocket.remote_address}. Total clients: {len(self.connected_clients)}")
        # Send welcome handshake
        welcome = {
            "type": "CONNECTION_ESTABLISHED",
            "message": "ErgoGuard AI Event Transport Connected",
            "server_time": time.time()
        }
        await websocket.send(json.dumps(welcome))

        # Immediately dispatch initial state to newly connected client
        if self.on_connect_callback:
            try:
                init_state = self.on_connect_callback()
                if init_state:
                    await websocket.send(json.dumps(init_state))
            except Exception as e:
                logger.debug(f"Failed to dispatch initial connect state: {e}")

    async def unregister(self, websocket):
        self.connected_clients.discard(websocket)
        if websocket in self._pending_video_tasks:
            task = self._pending_video_tasks.pop(websocket)
            task.cancel()
        logger.info(f"Frontend client disconnected. Remaining clients: {len(self.connected_clients)}")

    async def broadcast_telemetry(self, event_data: Dict[str, Any]):
        """
        High-Priority: Dispatches safety events, risk scores, and violation alerts.
        Guaranteed zero-drop delivery without carrying heavy video payloads.
        """
        if not self.connected_clients:
            return

        # Ensure type is explicitly set for frontend discrimination
        if "type" not in event_data:
            event_data["type"] = "SAFETY_TELEMETRY"

        message = json.dumps(event_data)
        dead_clients = set()
        for client in list(self.connected_clients):
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                dead_clients.add(client)
            except Exception as e:
                logger.warning(f"Error sending telemetry: {e}")
                dead_clients.add(client)

        for dc in dead_clients:
            await self.unregister(dc)

    async def broadcast_video_frame(self, frame_b64: str, metrics: Optional[Dict[str, Any]] = None):
        """
        High-Bandwidth: Dispatches compressed 640x360 video frames independently.
        Applies frame dropping if consumer connection has backpressure.
        """
        if not self.connected_clients or not frame_b64:
            return

        t0 = time.perf_counter()
        payload = {
            "type": "VIDEO_FRAME",
            "frame_image": frame_b64,
            "timestamp": time.time(),
            "metrics": metrics or {}
        }
        message = json.dumps(payload)
        t_serialize = (time.perf_counter() - t0) * 1000.0

        for client in list(self.connected_clients):
            # If client is already transmitting a previous frame, drop this intermediate frame!
            existing_task = self._pending_video_tasks.get(client)
            if existing_task is not None and not existing_task.done():
                # Stale frame dropped to prevent network buffering lag
                continue

            async def _send_frame(ws, msg):
                t_tx0 = time.perf_counter()
                try:
                    await ws.send(msg)
                    self.last_tx_ms = round((time.perf_counter() - t_tx0) * 1000.0 + t_serialize, 2)
                except websockets.exceptions.ConnectionClosed:
                    await self.unregister(ws)
                except Exception as ex:
                    logger.debug(f"Video frame dispatch dropped: {ex}")

            self._pending_video_tasks[client] = asyncio.create_task(_send_frame(client, message))

    async def broadcast_event(self, event_data: Dict[str, Any]):
        """Backward compatible broadcast interface."""
        # If event carries a frame_image, split it into telemetry + video
        frame_img = event_data.get("frame_image")
        clean_event = {k: v for k, v in event_data.items() if k != "frame_image"}
        await self.broadcast_telemetry(clean_event)
        if frame_img:
            await self.broadcast_video_frame(frame_img, clean_event.get("metrics"))

    async def handler(self, websocket):
        await self.register(websocket)
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    logger.info(f"Received command from frontend: {data}")
                    if self.on_command_callback:
                        cmd = data.get("command") or data.get("type", "UNKNOWN")
                        self.on_command_callback(cmd, data)
                except json.JSONDecodeError:
                    logger.warning(f"Non-JSON message received: {message}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister(websocket)

    async def start(self):
        logger.info(f"Starting ErgoGuard WebSocket server on ws://{self.host}:{self.port}")
        self._server = await websockets.serve(
            self.handler,
            self.host,
            self.port,
            max_size=10 * 1024 * 1024  # 10MB limit for Base64 frames
        )
        return self._server
