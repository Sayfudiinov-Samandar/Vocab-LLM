from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class WordBase(BaseModel):
    word: str = Field(..., min_length=1, max_length=100)

class WordCreate(WordBase):
    user_id: int = 1

class WordResponse(BaseModel):
    id: int
    user_id: int
    word: str
    phonetic: Optional[str]
    part_of_speech: Optional[str]
    chinese_meaning: Optional[str]
    example_sentence: str
    chinese_translation: Optional[str]
    source_name: Optional[str]
    source_url: str
    collocations: Optional[str]
    synonyms: Optional[str]
    antonyms: Optional[str]
    created_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class ReviewResponse(WordResponse):
    ease_factor: float
    interval_days: int
    review_count: int

class TelegramMessage(BaseModel):
    message_id: int
    chat_id: int
    text: str
    username: Optional[str] = None