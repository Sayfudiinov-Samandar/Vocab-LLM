"""OpenClaw integration wrapper.

The project exposes a stable local adapter even when the installed OpenClaw
package cannot be imported or its runtime API is different from this demo app.
This keeps Telegram/OpenClaw flows working for the final project while still
recording whether the package was available.
"""

from dataclasses import dataclass
from backend.config import settings

try:
    import cmdop.exceptions as cmdop_exceptions

    if not hasattr(cmdop_exceptions, "TimeoutError") and hasattr(cmdop_exceptions, "ConnectionTimeoutError"):
        cmdop_exceptions.TimeoutError = cmdop_exceptions.ConnectionTimeoutError
    from openclaw import OpenClaw as OpenClawRuntime
    OPENCLAW_IMPORT_ERROR = ""
except Exception as exc:
    OpenClawRuntime = None
    OPENCLAW_IMPORT_ERROR = str(exc)


@dataclass
class OpenClawAdapter:
    platform: str
    token: str
    webhook_url: str
    config_path: str
    runtime_available: bool = False
    runtime_error: str = ""

def create_openclaw_app():
    """Initialize OpenClaw metadata for Telegram/OpenClaw gateway demos."""
    payload = {
        "platform": "telegram",
        "token": settings.TELEGRAM_BOT_TOKEN,
        "webhook_url": f"{settings.WEBHOOK_URL}/telegram/webhook",
        "config_path": "config/openclaw/config.yaml",
    }

    return OpenClawAdapter(
        **payload,
        runtime_available=OpenClawRuntime is not None,
        runtime_error=OPENCLAW_IMPORT_ERROR,
    )
