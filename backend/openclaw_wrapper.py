"""
OpenClaw Integration Wrapper
Routes Telegram webhooks through OpenClaw configuration
"""

from openclaw import OpenClaw
from backend.config import settings

def create_openclaw_app():
    """Initialize OpenClaw with Telegram platform."""
    return OpenClaw(
        platform="telegram",
        token=settings.TELEGRAM_BOT_TOKEN,
        webhook_url=f"{settings.WEBHOOK_URL}/telegram/webhook",
        config_path="openclaw/config.yaml"
    )