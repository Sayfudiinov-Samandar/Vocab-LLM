import json
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional
from io import StringIO
import csv
from .database import (
    get_words, get_word_by_id, get_word_by_name, 
    delete_word, get_due_reviews, get_all_review_words, update_word,
    get_review_history, get_learning_records, get_learning_stats,
    get_quiz_question, update_review
)
from .schemas import WordResponse, WordCreate, WordUpdate, StatsResponse, QuizSubmit
from .agent import ExampleSearchAgent

router = APIRouter(prefix="/api")

@router.get("/words", response_model=List[WordResponse])
async def list_words(user_id: int = Query(default=1), q: Optional[str] = Query(default=None)):
    return get_words(user_id, q=q)

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
    if request.tags:
        update_word(
            result["word_id"],
            request.user_id,
            {"tags": json.dumps(request.tags, ensure_ascii=False)},
        )
        result["tags"] = request.tags
    return result

@router.post("/agent/example-search")
async def example_search_agent(request: WordCreate):
    return await create_word(request)

@router.post("/vocab/add")
async def add_vocab_alias(request: WordCreate):
    return await create_word(request)

@router.get("/vocab", response_model=List[WordResponse])
async def list_vocab_alias(user_id: int = Query(default=1), q: Optional[str] = Query(default=None)):
    return get_words(user_id, q=q)

@router.get("/vocab/export.csv")
async def export_vocab_csv(user_id: int = Query(default=1)):
    words = get_words(user_id, limit=1000)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "word",
        "phonetic",
        "part_of_speech",
        "chinese_meaning",
        "english_definition",
        "example_sentence",
        "chinese_translation",
        "source_name",
        "source_url",
        "source_type",
        "difficulty",
        "favorite",
        "tags",
        "created_at",
    ])
    for word in words:
        writer.writerow([
            word.get("word"),
            word.get("phonetic"),
            word.get("part_of_speech"),
            word.get("chinese_meaning"),
            word.get("english_definition"),
            word.get("example_sentence"),
            word.get("chinese_translation"),
            word.get("source_name"),
            word.get("source_url"),
            word.get("source_type"),
            word.get("difficulty"),
            word.get("favorite"),
            word.get("tags"),
            word.get("created_at"),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=vocabulary.csv"},
    )

@router.get("/vocab/{word}")
async def get_vocab_by_word_alias(word: str, user_id: int = Query(default=1)):
    result = get_word_by_name(word.lower(), user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Word not found")
    return result

@router.put("/words/{word_id}", response_model=WordResponse)
async def edit_word(word_id: int, request: WordUpdate, user_id: int = Query(default=1)):
    payload = request.model_dump(exclude_unset=True)
    for field in ("collocations", "synonyms", "antonyms", "tags"):
        if field in payload and payload[field] is not None:
            payload[field] = json.dumps(payload[field], ensure_ascii=False)

    updated = update_word(word_id, user_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Word not found")
    return updated

@router.put("/vocab/{word_id}", response_model=WordResponse)
async def edit_vocab_alias(word_id: int, request: WordUpdate, user_id: int = Query(default=1)):
    return await edit_word(word_id, request, user_id)

@router.delete("/words/{word_id}")
async def remove_word(word_id: int, user_id: int = Query(default=1)):
    deleted = delete_word(word_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Word not found")
    return {"message": "Deleted successfully"}

@router.delete("/vocab/{word_id}")
async def remove_vocab_alias(word_id: int, user_id: int = Query(default=1)):
    return await remove_word(word_id, user_id)

@router.get("/review/due")
async def get_due_words(user_id: int = Query(default=1), all_words: bool = Query(default=False)):
    if all_words:
        return get_all_review_words(user_id)
    return get_due_reviews(user_id)

@router.get("/review/all")
async def get_all_review_queue(user_id: int = Query(default=1)):
    return get_all_review_words(user_id)

@router.post("/review/{word_id}")
async def submit_review(word_id: int, known: bool = True, user_id: int = Query(default=1)):
    quality = 4 if known else 1
    update_review(word_id, user_id, quality)
    return {"message": "Marked as known!" if known else "Marked for review."}

@router.post("/review")
async def submit_review_body(payload: QuizSubmit):
    update_review(payload.word_id, payload.user_id, 5 if payload.selected_index == payload.correct_index else 1)
    return {"correct": payload.selected_index == payload.correct_index}

@router.get("/quiz")
async def quiz_question(user_id: int = Query(default=1)):
    question = get_quiz_question(user_id)
    if not question:
        raise HTTPException(status_code=400, detail="Need at least 4 words with meanings for quiz.")
    return question

@router.post("/quiz")
async def submit_quiz(payload: QuizSubmit):
    correct = payload.selected_index == payload.correct_index
    update_review(payload.word_id, payload.user_id, 5 if correct else 1)
    return {"correct": correct, "message": "Correct" if correct else "Review this word again"}

@router.get("/review/history")
async def review_history(user_id: int = Query(default=1), limit: int = Query(default=50, le=200)):
    return get_review_history(user_id, limit=limit)

@router.get("/learning/records")
async def learning_records(user_id: int = Query(default=1), limit: int = Query(default=50, le=200)):
    return get_learning_records(user_id, limit=limit)

@router.get("/stats", response_model=StatsResponse)
async def stats(user_id: int = Query(default=1)):
    return get_learning_stats(user_id)

@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "vocab-assistant"}
