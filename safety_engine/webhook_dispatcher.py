"""
ErgoGuard AI - Enterprise Webhook Dispatcher
Optional Layer 5 integration for enterprise safety monitoring systems.
Features:
- Configurable endpoint & authorization headers via environment or constructor
- Explicit enable/disable setting (disabled by default)
- Payload sanitization (strips frame buffers, transmits only validated metadata)
- Non-blocking asynchronous dispatch with timeout (default 3.0s) and failure recovery
- Zero extra dependencies (uses standard library urllib.request with asyncio)
"""

import os
import json
import asyncio
import logging
from typing import Optional, Dict, Any
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

logger = logging.getLogger("ErgoGuard.Webhook")

class WebhookDispatcher:
    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        enabled: Optional[bool] = None,
        secret_token: Optional[str] = None,
        timeout_sec: float = 3.0,
        max_retries: int = 2
    ):
        # Configuration resolution: constructor args take precedence, then environment
        self.endpoint_url = endpoint_url or os.environ.get("ERGOGUARD_WEBHOOK_URL", "")
        
        if enabled is not None:
            self.enabled = enabled
        else:
            self.enabled = os.environ.get("ERGOGUARD_WEBHOOK_ENABLED", "false").lower() in ("true", "1", "yes")

        self.secret_token = secret_token or os.environ.get("ERGOGUARD_WEBHOOK_SECRET", "")
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries

        # Operational metrics
        self.dispatched_count = 0
        self.failed_count = 0
        self.last_status: Optional[str] = None

    def is_active(self) -> bool:
        """Returns True if webhook dispatching is configured and enabled."""
        return self.enabled and bool(self.endpoint_url)

    def sanitize_payload(self, event_or_incident: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitizes payload before transmission to guarantee privacy and bandwidth efficiency.
        Explicitly removes frame buffers, binary data, and internal references.
        """
        clean = {}
        excluded_keys = {"frame", "image", "raw_frame", "buffer", "canvas", "cv2", "landmarks_raw"}

        for k, v in event_or_incident.items():
            if k in excluded_keys:
                continue
            if isinstance(v, str) and (v.startswith("data:image/") or len(v) > 2048):
                continue
            clean[k] = v

        clean["_dispatcher"] = "ErgoGuard_Enterprise_Webhook_v1"
        return clean

    def _sync_post(self, payload_bytes: bytes) -> bool:
        """Synchronous HTTP POST executed in thread pool."""
        req = Request(
            self.endpoint_url,
            data=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "ErgoGuard-AI/1.0 (Enterprise Safety Monitor)",
                **({"Authorization": f"Bearer {self.secret_token}"} if self.secret_token else {})
            },
            method="POST"
        )
        try:
            with urlopen(req, timeout=self.timeout_sec) as resp:
                status_code = resp.getcode()
                return 200 <= status_code < 300
        except (HTTPError, URLError, TimeoutError, OSError) as e:
            logger.warning(f"[WebhookDispatcher] Dispatch failed: {e}")
            return False

    async def dispatch(self, event_or_incident: Dict[str, Any]) -> bool:
        """
        Non-blocking async dispatch to enterprise webhook endpoint.
        Returns immediately if webhook is disabled or not configured.
        """
        if not self.is_active():
            return False

        sanitized = self.sanitize_payload(event_or_incident)
        try:
            payload_json = json.dumps(sanitized)
            payload_bytes = payload_json.encode("utf-8")
        except (TypeError, ValueError) as e:
            logger.error(f"[WebhookDispatcher] Serialization error: {e}")
            self.failed_count += 1
            self.last_status = f"SERIALIZATION_ERROR: {e}"
            return False

        # Execute non-blocking in standard asyncio thread pool
        loop = asyncio.get_running_loop()
        success = False
        for attempt in range(self.max_retries + 1):
            try:
                success = await loop.run_in_executor(None, self._sync_post, payload_bytes)
                if success:
                    self.dispatched_count += 1
                    self.last_status = "OK"
                    return True
                await asyncio.sleep(0.5 * (attempt + 1))
            except Exception as e:
                logger.debug(f"[WebhookDispatcher] Attempt {attempt+1} failed: {e}")

        self.failed_count += 1
        self.last_status = "DISPATCH_FAILED"
        return False
