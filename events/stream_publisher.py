"""Fire-and-forget publisher: sends a classified event to event-stream-service."""

import json
import logging
import time
import urllib.request
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_TIMEOUT_S = 2


def _make_jwt(secret: str) -> str:
    """Build a short-lived HS256 JWT for authenticating to event-stream-service."""
    import base64
    import hashlib
    import hmac

    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    now = int(time.time())
    claims = json.dumps({"sub": "observaboard", "iat": now, "exp": now + 60}, separators=(",", ":"))
    payload = base64.urlsafe_b64encode(claims.encode()).rstrip(b"=").decode()

    signing_input = f"{header}.{payload}".encode()
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()

    return f"{header}.{payload}.{signature}"


def publish_to_stream(event, stream_url: str, jwt_secret: str) -> None:
    """
    POST a classified event to event-stream-service.

    All exceptions are swallowed - failure to publish must never break the
    ingest response. This is deliberately synchronous with a 2-second timeout
    to keep the code simple (Celery was removed in v1.6).
    """
    if not stream_url or not jwt_secret:
        return

    try:
        body = json.dumps({
            "source": event.source,
            "type": event.event_type,
            "payload": {
                "category": event.category,
                "severity": event.severity,
                "summary": event.summary,
                "path": event.raw_payload.get("path") if isinstance(event.raw_payload, dict) else None,
            },
        }).encode()

        token = _make_jwt(jwt_secret)
        req = urllib.request.Request(
            url=stream_url.rstrip("/") + "/events/publish",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S):
            pass

        logger.debug("Published event %s (%s) to stream", event.id, event.event_type)

    except Exception:
        logger.warning("Failed to publish event %s to stream", event.id, exc_info=True)
