from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from .database import (
    get_words, get_word_by_id, get_word_by_name, 
    delete_word, get_or_create_user, get_due_reviews
)
from .schemas import WordResponse, WordCreate
from .agent import ExampleSearchAgent

router = APIRouter(prefix="/api")

@router.get("/words", response_model=List[WordResponse])
async def list_words(user_id: int = Query(default=1)):
    return get_words(user_id)

@router.get("/words/search")
async def search_word(q: str, user_id: int = Query(default=1)):
    word = get_word_by_name(q.lower(), user_id)
    if not word:
        raise HTTPException(status_code=404, detail=f"Word '{q}' not found")
    return word

@router.get("/words/{word_id}", response_model=WordResponse)
async def get_word(word_id: int):
    word = get_word_by_id(word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    return word

@router.post("/words")
async def create_word(request: WordCreate):
    agent = ExampleSearchAgent()
    result = await agent.execute(request.word, user_id=request.user_id)
    return result

@router.delete("/words/{word_id}")
async def remove_word(word_id: int, user_id: int = Query(default=1)):
    deleted = delete_word(word_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Word not found")
    return {"message": "Deleted successfully"}

@router.get("/review/due")
async def get_due_words(user_id: int = Query(default=1)):
    return get_due_reviews(user_id)

@router.post("/review/{word_id}")
async def submit_review(word_id: int, known: bool = True, user_id: int = Query(default=1)):
    from backend.database import update_review
    quality = 4 if known else 1
    update_review(word_id, user_id, quality)
    return {"message": "Marked as known!" if known else "Marked for review."}

@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "vocab-assistant"}