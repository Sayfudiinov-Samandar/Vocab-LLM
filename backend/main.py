from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .openclaw_gateway import router as openclaw_gateway_router
from .openclaw_wrapper import create_openclaw_app
from .telegram_bot import poll_telegram_updates, router as telegram_router, set_webhook
from .web_routes import router as web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up...")
    init_db()
    telegram_polling_stop = None
    telegram_polling_task = None

    openclaw_app = create_openclaw_app()
    print(f"OpenClaw initialized: {openclaw_app.platform}")
    if openclaw_app.runtime_error:
        print(f"OpenClaw runtime fallback: {openclaw_app.runtime_error}")

    delivery_mode = settings.TELEGRAM_DELIVERY.lower()
    if delivery_mode == "disabled":
        print("Telegram delivery mode: disabled")
    elif delivery_mode == "polling":
        import asyncio

        telegram_polling_stop = asyncio.Event()
        telegram_polling_task = asyncio.create_task(poll_telegram_updates(telegram_polling_stop))
        print("Telegram delivery mode: polling")
    else:
        await set_webhook()
        print("Telegram delivery mode: webhook")

    print("Ready")
    yield
    if telegram_polling_stop and telegram_polling_task:
        telegram_polling_stop.set()
        telegram_polling_task.cancel()
    print("Shutting down...")


app = FastAPI(
    title="AI Vocabulary Assistant",
    description="AI-powered vocabulary with real news examples",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(web_router)
app.include_router(telegram_router)
app.include_router(openclaw_gateway_router)

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
