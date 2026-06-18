import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .agent import ExampleSearchAgent
from .database import (
    delete_word,
    get_due_reviews,
    get_learning_stats,
    get_or_create_user,
    get_quiz_question,
    get_word_by_name,
    get_words,
    update_review,
    update_word,
)
from .openclaw_wrapper import create_openclaw_app
from .telegram_bot import log_openclaw_step, parse_command

router = APIRouter(prefix="/openclaw", tags=["openclaw"])


class OpenClawGatewayRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=300)
    telegram_id: str = "openclaw-gateway-demo"
    username: Optional[str] = "openclaw"
    user_id: Optional[int] = None


def _json_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else []
    except Exception:
        return []


def _word_payload(word: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(word)
    for field in ("collocations", "synonyms", "antonyms", "tags"):
        payload[field] = _json_list(payload.get(field))
    return payload


def _resolve_user(payload: OpenClawGatewayRequest) -> int:
    if payload.user_id:
        return payload.user_id
    user = get_or_create_user(telegram_id=payload.telegram_id, username=payload.username)
    return user["id"]


@router.get("/health")
async def openclaw_health():
    app = create_openclaw_app()
    return {
        "status": "ok",
        "platform": app.platform,
        "gateway": "/openclaw/gateway",
        "telegram_webhook": app.webhook_url,
        "runtime_available": app.runtime_available,
        "runtime_error": app.runtime_error,
    }


@router.get("/onboarding")
async def openclaw_onboarding():
    app = create_openclaw_app()
    return {
        "project": "ai-vocab-assistant",
        "platform": app.platform,
        "local_mode": {
            "telegram_delivery": "polling",
            "web_app": "http://localhost:8000",
            "gateway": "http://localhost:8000/openclaw/gateway",
            "health": "http://localhost:8000/openclaw/health",
        },
        "public_mode": {
            "telegram_delivery": "webhook",
            "telegram_webhook": app.webhook_url,
            "gateway": f"{app.webhook_url.rsplit('/telegram/webhook', 1)[0]}/openclaw/gateway",
        },
        "required_env": [
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_DELIVERY",
            "WEBHOOK_URL",
            "TAVILY_API_KEY",
            "QWEN_API_KEY",
            "DATABASE_URL",
        ],
        "commands": [
            "add sanction",
            "query sanction",
            "update sanction | final project demo word",
            "list",
            "review",
            "quiz",
            "stats",
            "delete sanction",
        ],
        "demo_order": [
            "Start backend with uvicorn.",
            "Open /openclaw/health.",
            "Send a gateway command to /openclaw/gateway.",
            "Send /start in Telegram.",
            "Send add sanction in Telegram and show terminal OpenClaw logs.",
            "Show the saved word in the web dashboard.",
            "Switch to TELEGRAM_DELIVERY=webhook after public deployment.",
        ],
    }


@router.post("/gateway")
async def openclaw_gateway(payload: OpenClawGatewayRequest):
    log_openclaw_step("gateway", 1, 5, f"Receive gateway text: {payload.text}")
    user_id = _resolve_user(payload)
    log_openclaw_step("gateway", 2, 5, f"Resolve gateway user_id={user_id}")
    command, argument = parse_command(payload.text)
    log_openclaw_step("gateway", 3, 5, f"Parse command='{command}', argument='{argument}'")

    if command in {"start", "help", "menu"}:
        response = "Commands: add WORD, query WORD, update WORD | notes, list, review, quiz, stats, delete WORD"
        log_openclaw_step("gateway", 4, 5, "Build help response")
        log_openclaw_step("gateway", 5, 5, "Return help response")
        return {"ok": True, "command": command, "response": response}

    if command == "add" and argument:
        log_openclaw_step("gateway", 4, 5, "Run Example Search Agent")
        result = await ExampleSearchAgent().execute(argument, user_id=user_id)
        response = f"Saved {result['word']} from {result.get('source') or 'AI fallback'}."
        log_openclaw_step("gateway", 5, 5, "Return add result")
        return {"ok": True, "command": command, "response": response, "data": result}

    if command == "query" and argument:
        log_openclaw_step("gateway", 4, 5, "Query vocabulary database")
        result = get_word_by_name(argument.lower(), user_id)
        if not result:
            log_openclaw_step("gateway", 5, 5, "Word not found")
            raise HTTPException(status_code=404, detail=f"{argument} was not found")
        log_openclaw_step("gateway", 5, 5, "Return query result")
        return {"ok": True, "command": command, "response": f"Found {result['word']}.", "data": _word_payload(result)}

    if command == "delete" and argument:
        log_openclaw_step("gateway", 4, 5, "Delete vocabulary word")
        result = get_word_by_name(argument.lower(), user_id)
        if not result:
            log_openclaw_step("gateway", 5, 5, "Word not found")
            raise HTTPException(status_code=404, detail=f"{argument} was not found")
        delete_word(result["id"], user_id)
        log_openclaw_step("gateway", 5, 5, "Return delete confirmation")
        return {"ok": True, "command": command, "response": f"Deleted {argument}."}

    if command == "update" and argument:
        log_openclaw_step("gateway", 4, 5, "Update saved word notes")
        parts = [part.strip() for part in argument.split("|", maxsplit=1)]
        word = parts[0].lower()
        notes = parts[1] if len(parts) > 1 else "Updated through OpenClaw gateway."
        result = get_word_by_name(word, user_id)
        if not result:
            log_openclaw_step("gateway", 5, 5, "Word not found")
            raise HTTPException(status_code=404, detail=f"{word} was not found")
        updated = update_word(result["id"], user_id, {"notes": notes})
        log_openclaw_step("gateway", 5, 5, "Return update result")
        return {"ok": True, "command": command, "response": f"Updated {word}.", "data": _word_payload(updated)}

    if command == "list":
        log_openclaw_step("gateway", 4, 5, "List saved vocabulary")
        words = [_word_payload(word) for word in get_words(user_id, limit=20)]
        log_openclaw_step("gateway", 5, 5, "Return vocabulary list")
        return {"ok": True, "command": command, "response": f"{len(words)} words returned.", "data": words}

    if command == "review":
        log_openclaw_step("gateway", 4, 5, "Load due review words")
        due = get_due_reviews(user_id)
        log_openclaw_step("gateway", 5, 5, "Return review item")
        return {
            "ok": True,
            "command": command,
            "response": "No words due." if not due else f"Review {due[0]['word']}.",
            "data": _word_payload(due[0]) if due else None,
        }

    if command == "reviewed" and argument:
        log_openclaw_step("gateway", 4, 5, "Save review result")
        parts = argument.split()
        if len(parts) < 2:
            raise HTTPException(status_code=400, detail="Use: reviewed WORD good|again")
        word = get_word_by_name(parts[0].lower(), user_id)
        if not word:
            raise HTTPException(status_code=404, detail=f"{parts[0]} was not found")
        known = parts[1].lower() in {"good", "known", "yes", "correct"}
        update_review(word["id"], user_id, 4 if known else 1)
        log_openclaw_step("gateway", 5, 5, "Return review confirmation")
        return {"ok": True, "command": command, "response": f"Review saved for {word['word']}."}

    if command == "quiz":
        log_openclaw_step("gateway", 4, 5, "Build quiz question")
        question = get_quiz_question(user_id)
        if not question:
            log_openclaw_step("gateway", 5, 5, "Not enough words for quiz")
            raise HTTPException(status_code=400, detail="Need at least 4 words for quiz")
        log_openclaw_step("gateway", 5, 5, "Return quiz question")
        return {"ok": True, "command": command, "response": f"Quiz word: {question['word']}.", "data": question}

    if command == "stats":
        log_openclaw_step("gateway", 4, 5, "Load learning statistics")
        stats = get_learning_stats(user_id)
        log_openclaw_step("gateway", 5, 5, "Return stats")
        return {"ok": True, "command": command, "response": "Learning stats returned.", "data": stats}

    log_openclaw_step("gateway", 4, 5, "Reject unsupported command")
    log_openclaw_step("gateway", 5, 5, "Return unsupported command error")
    raise HTTPException(status_code=400, detail="Unsupported command")
