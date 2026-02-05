"""Outbound webhook dispatch: POST JSON payload with HMAC-SHA256 signature."""

import hashlib
import hmac
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.utils import timezone

logger = logging.getLogger(__name__)


def _sign_payload(secret: str, body: bytes) -> str:
    if not secret:
        return ""
    return hmac.new(
        secret.encode("utf-8") if isinstance(secret, str) else secret,
        body,
        hashlib.sha256,
    ).hexdigest()


def dispatch_webhooks(event_name: str, payload: dict) -> None:
    """Find active webhooks subscribed to this event and POST payload with X-Webhook-Signature."""
    from .models import Webhook

    webhooks = Webhook.objects.filter(
        is_active=True,
        events__contains=[event_name],
    )
    body = json.dumps(payload, default=str).encode("utf-8")
    for wh in webhooks:
        try:
            signature = _sign_payload(wh.secret, body)
            req = Request(
                wh.url,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature,
                    "X-Webhook-Event": event_name,
                },
                method="POST",
            )
            urlopen(req, timeout=10)
        except (URLError, HTTPError, OSError) as e:
            logger.warning("Webhook %s (%s) failed: %s", wh.name, wh.url, e)


def build_webhook_payload(
    event_name: str,
    model_name: str,
    object_id,
    object_repr: str,
    old_values: dict,
    new_values: dict,
) -> dict:
    return {
        "event": event_name,
        "model": model_name,
        "object_id": object_id,
        "object_repr": object_repr,
        "old_values": old_values,
        "new_values": new_values,
        "timestamp": timezone.now().isoformat(),
    }
