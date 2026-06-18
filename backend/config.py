import os
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # API Keys
    TAVILY_API_KEY: str
    QWEN_API_KEY: str
    TELEGRAM_BOT_TOKEN: str
    
    # Qwen Config
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-plus"
    
    # Tavily Config
    TAVILY_MAX_RESULTS: int = 3
    
    # App Config
    DATABASE_URL: str = "sqlite:///./data/vocab.db"
    WEBHOOK_URL: str
    SECRET_KEY: str = "default-secret-key-change-in-production"

    # Telegram delivery: "polling" for local development, "webhook" for public deployment.
    TELEGRAM_DELIVERY: str = "polling"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # <-- ADD THIS LINE

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
