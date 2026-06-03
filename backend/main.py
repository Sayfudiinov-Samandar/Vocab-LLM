from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .database import init_db
from .web_routes import router as web_router
from .telegram_bot import router as telegram_router, set_webhook

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting up...")
    init_db()
    await set_webhook()
    print("✅ Ready")
    yield
    print("🛑 Shutting down...")

app = FastAPI(
    title="AI Vocabulary Assistant",
    description="AI-powered vocabulary with real news examples",
    version="1.0.0",
    lifespan=lifespan
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

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)