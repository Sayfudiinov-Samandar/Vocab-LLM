from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class WordBase(BaseModel):
    word: str = Field(..., min_length=1, max_length=100)

class WordCreate(WordBase):
    user_id: int = 1
    tags: List[str] = Field(default_factory=list)

class WordUpdate(BaseModel):
    word: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phonetic: Optional[str] = None
    part_of_speech: Optional[str] = None
    chinese_meaning: Optional[str] = None
    english_definition: Optional[str] = None
    example_sentence: Optional[str] = None
    chinese_translation: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    source_type: Optional[str] = None
    collocations: Optional[List[str]] = None
    synonyms: Optional[List[str]] = None
    antonyms: Optional[List[str]] = None
    memory_tip: Optional[str] = None
    difficulty: Optional[int] = Field(default=None, ge=1, le=5)
    favorite: Optional[bool] = None
    tags: Optional[List[str]] = None
    audio_url: Optional[str] = None
    notes: Optional[str] = None

class WordResponse(BaseModel):
    id: int
    user_id: int
    word: str
    phonetic: Optional[str]
    part_of_speech: Optional[str]
    chinese_meaning: Optional[str]
    english_definition: Optional[str] = None
    example_sentence: str
    chinese_translation: Optional[str]
    source_name: Optional[str]
    source_url: str
    source_type: Optional[str] = "authentic"
    collocations: Optional[str]
    synonyms: Optional[str]
    antonyms: Optional[str]
    memory_tip: Optional[str] = None
    difficulty: Optional[int] = 2
    favorite: Optional[int] = 0
    tags: Optional[str] = "[]"
    audio_url: Optional[str] = None
    notes: Optional[str] = None
    updated_at: Optional[datetime] = None
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

class StatsResponse(BaseModel):
    total_words: int
    due_reviews: int
    maturing_words: int
    total_reviews: int
    reviews_today: int
    tag_counts: dict

class QuizSubmit(BaseModel):
    word_id: int
    selected_index: int
    correct_index: int
    user_id: int = 1
