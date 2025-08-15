"""
Shared FastAPI dependencies.

Contains small reusable auth checks for webhooks.
"""

from fastapi import Request, HTTPException, status, Depends
import logging

from app.core.config import settings


logger = logging.getLogger(__name__)


def require_webhook_secret(request: Request) -> None:
    """
    Require a static secret header for incoming webhooks.

    Expects header: X-Webhook-Secret
    Compares against settings.webhook_secret.
    """
    provided = request.headers.get("x-webhook-secret") or request.headers.get("X-Webhook-Secret")
    expected = settings.webhook_secret

    if not provided or provided != expected:
        logger.warning("Webhook auth failed: missing/invalid secret")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized webhook")

    logger.debug("Webhook authenticated successfully")


