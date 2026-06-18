import asyncio
import json

from fastapi import APIRouter, Request
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode

from backend.agent import ExampleSearchAgent
from backend.config import settings
from backend.database import (
    delete_word,
    get_due_reviews,
    get_learning_stats,
    get_or_create_user,
    get_word_by_name,
    get_words,
    update_review,
    update_word,
)

router = APIRouter(prefix="/telegram")
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

# Simple in-memory state storage for menu-driven Telegram demos.
user_states = {}


def log_openclaw_step(command: str, step: int, total: int, message: str):
    print(f"[OpenClaw][{command}] {step}/{total} {message}")


def parse_command(text: str):
    cleaned = text.strip()
    if cleaned.startswith("/"):
        cleaned = cleaned[1:]
    parts = cleaned.split(maxsplit=1)
    command = parts[0].lower() if parts else ""
    argument = parts[1].strip().lower() if len(parts) > 1 else ""
    return command, argument


def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("Add Word", callback_data="menu_add")],
        [
            InlineKeyboardButton("Query Word", callback_data="menu_query"),
            InlineKeyboardButton("My List", callback_data="menu_list"),
        ],
        [
            InlineKeyboardButton("Review", callback_data="menu_review"),
            InlineKeyboardButton("Quiz", callback_data="menu_quiz"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Back to Menu", callback_data="menu_main")]])


def _json_list(value, default=None):
    if default is None:
        default = []
    if not value:
        return default
    if isinstance(value, list):
        return value
    try:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else default
    except Exception:
        return default


def _get_message_target(update_or_query):
    return update_or_query.message


async def start_command(update: Update, context=None):
    welcome = (
        "*AI Vocabulary Assistant*\n\n"
        "Learn English words with real news examples.\n\n"
        "Commands:\n"
        "`add abandon`\n"
        "`query abandon`\n"
        "`update abandon | exam word`\n"
        "`review`\n"
        "`quiz`\n"
        "`stats`\n"
        "`delete abandon`"
    )
    await update.message.reply_text(
        welcome,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard(),
    )


async def handle_callback(update: Update, context=None):
    query = update.callback_query
    await query.answer()

    data = query.data
    log_openclaw_step("callback", 1, 3, f"Receive button callback='{data}'")
    user = get_or_create_user(
        telegram_id=str(update.effective_user.id),
        username=update.effective_user.username,
    )
    user_id = user["id"]
    telegram_id = str(update.effective_user.id)
    log_openclaw_step("callback", 2, 3, f"Map Telegram callback user to user_id={user_id}")

    if data == "menu_main":
        await _safe_edit_or_reply(query, "*Main Menu*\n\nChoose an option:", main_menu_keyboard())
    elif data == "menu_add":
        user_states[telegram_id] = "waiting_for_word_to_add"
        await _safe_edit_or_reply(
            query,
            "*Add Word*\n\nType the word you want to add.\n\nExample: `economy`, `sanction`, `abandon`",
            back_keyboard(),
        )
    elif data == "menu_query":
        user_states[telegram_id] = "waiting_for_word_to_query"
        await _safe_edit_or_reply(query, "*Query Word*\n\nType the word you want to look up.", back_keyboard())
    elif data == "menu_list":
        await show_list(query, user_id, edit=True)
    elif data == "menu_review":
        await show_review(query, user_id, edit=True)
    elif data == "menu_quiz":
        await show_quiz(query, user_id, edit=True)
    elif data.startswith("know_"):
        await handle_review_result(query, int(data.split("_")[1]), user_id, known=True)
    elif data.startswith("dontknow_"):
        await handle_review_result(query, int(data.split("_")[1]), user_id, known=False)
    elif data.startswith("delete_"):
        await handle_delete(query, int(data.split("_")[1]), user_id)
    elif data.startswith("quiz_"):
        await handle_quiz_answer(query, data, user_id)

    log_openclaw_step("callback", 3, 3, f"Finished callback='{data}'")


async def _safe_edit_or_reply(query, text: str, reply_markup=None):
    try:
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    except Exception:
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


async def show_list(query, user_id, edit=False):
    log_openclaw_step("list", 1, 3, f"Load vocabulary list for user_id={user_id}")
    words = get_words(user_id, limit=20)
    log_openclaw_step("list", 2, 3, f"Format {len(words)} saved words")

    if not words:
        msg = "Your vocabulary is empty.\n\nUse `add sanction` to start."
    else:
        msg = "*Your Vocabulary* (last 20)\n\n"
        for index, word in enumerate(words, 1):
            msg += f"{index}. *{word['word']}* - {word.get('chinese_meaning') or 'No meaning yet'}\n"

    if edit:
        await _safe_edit_or_reply(query, msg, main_menu_keyboard())
    else:
        await _get_message_target(query).reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())
    log_openclaw_step("list", 3, 3, "Send vocabulary list to Telegram")


async def show_review(query, user_id, edit=False):
    log_openclaw_step("review", 1, 4, f"Load due review queue for user_id={user_id}")
    due = get_due_reviews(user_id)
    log_openclaw_step("review", 2, 4, f"Found {len(due)} due words")

    if not due:
        msg = "*No words due for review.*\n\nYou are all caught up."
        if edit:
            await _safe_edit_or_reply(query, msg, main_menu_keyboard())
        else:
            await _get_message_target(query).reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())
        log_openclaw_step("review", 4, 4, "Send no-due-words message")
        return

    word = due[0]
    log_openclaw_step("review", 3, 4, f"Select review word='{word['word']}'")
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("Again", callback_data=f"dontknow_{word['id']}"),
            InlineKeyboardButton("Good", callback_data=f"know_{word['id']}"),
        ]]
    )
    msg = (
        f"*Review Time* ({len(due)} words due)\n\n"
        f"*{word['word']}* `{word.get('phonetic') or ''}`\n\n"
        f"{word.get('example_sentence') or ''}\n\n"
        "Do you remember the meaning?"
    )

    if edit:
        await _safe_edit_or_reply(query, msg, keyboard)
    else:
        await _get_message_target(query).reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    log_openclaw_step("review", 4, 4, "Send review card with Again/Good buttons")


async def handle_review_result(query, word_id, user_id, known):
    log_openclaw_step("review-result", 1, 3, f"Receive review result word_id={word_id}, known={known}")
    quality = 4 if known else 1
    log_openclaw_step("review-result", 2, 3, f"Update spaced repetition quality={quality}")
    update_review(word_id, user_id, quality)

    await query.answer("Marked as known." if known else "Will review again soon.")
    await show_review(query, user_id, edit=False)
    log_openclaw_step("review-result", 3, 3, "Save review history and send next review card")


async def show_quiz(query, user_id, edit=False):
    import random

    log_openclaw_step("quiz", 1, 4, f"Load quiz word pool for user_id={user_id}")
    words = get_words(user_id, limit=50)
    log_openclaw_step("quiz", 2, 4, f"Found {len(words)} candidate words")

    if len(words) < 4:
        msg = "Need at least 4 words for a quiz.\n\nAdd more words first."
        if edit:
            await _safe_edit_or_reply(query, msg, main_menu_keyboard())
        else:
            await _get_message_target(query).reply_text(msg, reply_markup=main_menu_keyboard())
        log_openclaw_step("quiz", 4, 4, "Not enough words, send quiz requirement message")
        return

    target = random.choice(words)
    log_openclaw_step("quiz", 3, 4, f"Choose target word='{target['word']}' and prepare options")
    distractors = random.sample([word for word in words if word["id"] != target["id"]], 3)
    options = [target] + distractors
    random.shuffle(options)
    correct_idx = next(index for index, option in enumerate(options) if option["id"] == target["id"])

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"{chr(65 + index)}. {option.get('chinese_meaning') or 'No meaning'}", callback_data=f"quiz_{target['id']}_{index}_{correct_idx}")]
            for index, option in enumerate(options)
        ]
    )
    msg = f"*Quiz*\n\nWhat does *{target['word']}* mean?"

    if edit:
        await _safe_edit_or_reply(query, msg, keyboard)
    else:
        await _get_message_target(query).reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    log_openclaw_step("quiz", 4, 4, "Send quiz question with answer buttons")


async def handle_quiz_answer(query, data, user_id):
    log_openclaw_step("quiz-answer", 1, 3, f"Receive quiz answer callback='{data}'")
    _, target_id, selected_idx, correct_idx = data.split("_")
    target_id = int(target_id)
    selected_idx = int(selected_idx)
    correct_idx = int(correct_idx)
    known = selected_idx == correct_idx
    log_openclaw_step("quiz-answer", 2, 3, f"Evaluate selected={selected_idx}, correct={correct_idx}, known={known}")
    update_review(target_id, user_id, 5 if known else 1)

    if known:
        await query.answer("Correct.")
        await query.message.reply_text("Correct. Review progress saved.", reply_markup=main_menu_keyboard())
    else:
        await query.answer("Not quite.")
        word = next((item for item in get_words(user_id, limit=100) if item["id"] == target_id), None)
        meaning = word["chinese_meaning"] if word else "Check this word again."
        await query.message.reply_text(f"Not quite. Correct meaning: {meaning}", reply_markup=main_menu_keyboard())
    log_openclaw_step("quiz-answer", 3, 3, "Save quiz result to review history and send feedback")


async def handle_delete(query, word_id, user_id):
    log_openclaw_step("delete-button", 1, 3, f"Receive inline delete for word_id={word_id}")
    delete_word(word_id, user_id)
    log_openclaw_step("delete-button", 2, 3, "Delete vocabulary row from SQLite")
    await query.answer("Word deleted.")
    try:
        await query.edit_message_text("Word deleted successfully.", reply_markup=main_menu_keyboard())
    except Exception:
        await query.message.reply_text("Word deleted successfully.", reply_markup=main_menu_keyboard())
    log_openclaw_step("delete-button", 3, 3, "Send inline delete confirmation")


async def handle_text(update: Update, context=None):
    raw_text = update.message.text.strip()
    text = raw_text.lower()
    log_openclaw_step("message", 1, 4, f"Receive Telegram/OpenClaw text: {raw_text}")
    user = get_or_create_user(
        telegram_id=str(update.effective_user.id),
        username=update.effective_user.username,
    )
    user_id = user["id"]
    telegram_id = str(update.effective_user.id)
    log_openclaw_step("message", 2, 4, f"Map Telegram user to internal user_id={user_id}")

    state = user_states.get(telegram_id, "")
    if state == "waiting_for_word_to_add":
        user_states[telegram_id] = ""
        await add_word_flow(update, text, user_id)
        log_openclaw_step("message", 4, 4, "Finished menu add flow")
        return
    if state == "waiting_for_word_to_query":
        user_states[telegram_id] = ""
        await query_word_flow(update, text, user_id)
        log_openclaw_step("message", 4, 4, "Finished menu query flow")
        return

    command, argument = parse_command(raw_text)
    log_openclaw_step("message", 3, 4, f"Parse command='{command}', argument='{argument}'")

    if command in {"start", "menu"}:
        await start_command(update, None)
    elif command == "help":
        await update.message.reply_text(
            "Commands: add WORD, query WORD, update WORD | notes, list, review, quiz, stats, delete WORD",
            reply_markup=main_menu_keyboard(),
        )
    elif command == "add" and argument:
        await add_word_flow(update, argument, user_id)
    elif command == "query" and argument:
        await query_word_flow(update, argument, user_id)
    elif command == "delete" and argument:
        await delete_word_flow(update, argument, user_id)
    elif command == "update" and argument:
        await update_word_flow(update, argument, user_id)
    elif command == "list":
        await show_list(update, user_id, edit=False)
    elif command == "review":
        await show_review(update, user_id, edit=False)
    elif command == "quiz":
        await show_quiz(update, user_id, edit=False)
    elif command == "stats":
        await stats_flow(update, user_id)
    else:
        await add_word_flow(update, text, user_id)
    log_openclaw_step("message", 4, 4, f"Finished routing command='{command}'")


async def add_word_flow(update, word, user_id):
    log_openclaw_step("add", 1, 6, f"Receive add command for word='{word}'")
    loading_msg = await update.message.reply_text(f"Searching real news for *{word}*...", parse_mode=ParseMode.MARKDOWN)

    try:
        log_openclaw_step("add", 2, 6, "Create ExampleSearchAgent workflow")
        agent = ExampleSearchAgent()
        log_openclaw_step("add", 3, 6, "Run search -> extract -> enrich -> save pipeline")
        result = await agent.execute(word, user_id=user_id)
        log_openclaw_step("add", 4, 6, "Agent returned vocabulary data")

        if result.get("status") == "exists":
            log_openclaw_step("add", 5, 6, "Word already exists, skip duplicate insert")
            await loading_msg.edit_text(
                f"*{result['word']}* already exists.\n\nExample: {result['example']}\nTranslation: {result['translation']}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(),
            )
            log_openclaw_step("add", 6, 6, "Send existing-word response to Telegram")
            return

        collocations = "\n".join([f"- {item}" for item in result.get("collocations", [])]) or "No collocations yet."
        synonyms = ", ".join(result.get("synonyms", [])) or "None"
        antonyms = ", ".join(result.get("antonyms", [])) or "None"
        source_line = f"[{result['source']}]({result['url']})" if result.get("url") else result.get("source", "AI fallback")
        log_openclaw_step("add", 5, 6, "Format added-word Telegram response")

        msg = (
            "*Word Added!*\n\n"
            f"*{result['word']}* `{result['phonetic']}` *{result['pos']}*\n"
            f"Meaning: {result['meaning']}\n\n"
            f"*Example:*\n_{result['example']}_\n\n"
            f"*Translation:*\n{result['translation']}\n\n"
            f"*Source:* {source_line}\n\n"
            f"*Collocations:*\n{collocations}\n\n"
            f"*Synonyms:* {synonyms}\n"
            f"*Antonyms:* {antonyms}"
        )
        await loading_msg.edit_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
            reply_markup=main_menu_keyboard(),
        )
        log_openclaw_step("add", 6, 6, "Send added-word response to Telegram")
    except ValueError as error:
        log_openclaw_step("add", 6, 6, f"Validation failed: {error}")
        await loading_msg.edit_text(str(error), reply_markup=main_menu_keyboard())
    except Exception as error:
        print(f"[Add Error] {error}")
        log_openclaw_step("add", 6, 6, f"Unexpected error: {error}")
        await loading_msg.edit_text("Error searching for word. Try again.", reply_markup=main_menu_keyboard())


async def query_word_flow(update, word, user_id):
    log_openclaw_step("query", 1, 4, f"Receive query command for word='{word}'")
    result = get_word_by_name(word.lower(), user_id)
    log_openclaw_step("query", 2, 4, "Look up word in SQLite database")

    if not result:
        log_openclaw_step("query", 4, 4, "Word not found, send add suggestion")
        await update.message.reply_text(
            f"*{word}* was not found.\n\nUse `add {word}` to add it.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(),
        )
        return

    log_openclaw_step("query", 3, 4, "Format saved vocabulary details")
    collocations = "\n".join([f"- {item}" for item in _json_list(result.get("collocations"))]) or "No collocations yet."
    source_line = (
        f"[Source: {result['source_name']}]({result['source_url']})"
        if result.get("source_url")
        else f"Source: {result.get('source_name') or 'AI fallback'}"
    )
    msg = (
        f"*{result['word']}* `{result.get('phonetic') or ''}` *{result.get('part_of_speech') or ''}*\n"
        f"Meaning: {result.get('chinese_meaning') or ''}\n\n"
        f"*Example:*\n_{result.get('example_sentence') or ''}_\n\n"
        f"{result.get('chinese_translation') or ''}\n\n"
        f"{source_line}\n\n"
        f"*Collocations:*\n{collocations}"
    )
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("Delete", callback_data=f"delete_{result['id']}"),
            InlineKeyboardButton("Back", callback_data="menu_main"),
        ]]
    )
    await update.message.reply_text(
        msg,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )
    log_openclaw_step("query", 4, 4, "Send query result to Telegram")


async def delete_word_flow(update, word, user_id):
    log_openclaw_step("delete", 1, 4, f"Receive delete command for word='{word}'")
    result = get_word_by_name(word.lower(), user_id)
    log_openclaw_step("delete", 2, 4, "Look up word before deletion")
    if not result:
        log_openclaw_step("delete", 4, 4, "Word not found, send failure message")
        await update.message.reply_text(f"{word} was not found.", reply_markup=main_menu_keyboard())
        return

    log_openclaw_step("delete", 3, 4, f"Delete vocabulary and review rows for word_id={result['id']}")
    delete_word(result["id"], user_id)
    await update.message.reply_text(f"Deleted {word}.", reply_markup=main_menu_keyboard())
    log_openclaw_step("delete", 4, 4, "Send delete confirmation to Telegram")


async def update_word_flow(update, argument, user_id):
    log_openclaw_step("update", 1, 5, f"Receive update command argument='{argument}'")
    parts = [part.strip() for part in argument.split("|", maxsplit=1)]
    word = parts[0].lower()
    notes = parts[1] if len(parts) > 1 else "Updated through Telegram/OpenClaw command."
    log_openclaw_step("update", 2, 5, f"Parsed word='{word}', notes='{notes}'")

    result = get_word_by_name(word, user_id)
    log_openclaw_step("update", 3, 5, "Look up word in SQLite database")
    if not result:
        log_openclaw_step("update", 5, 5, "Word not found, send failure message")
        await update.message.reply_text(f"{word} was not found. Use `add {word}` first.", parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())
        return

    log_openclaw_step("update", 4, 5, f"Update notes for word_id={result['id']}")
    update_word(result["id"], user_id, {"notes": notes})
    await update.message.reply_text(f"Updated {word}.\n\nNotes: {notes}", reply_markup=main_menu_keyboard())
    log_openclaw_step("update", 5, 5, "Send update confirmation to Telegram")


async def stats_flow(update, user_id):
    log_openclaw_step("stats", 1, 3, f"Load learning statistics for user_id={user_id}")
    stats = get_learning_stats(user_id)
    log_openclaw_step("stats", 2, 3, "Format learning statistics response")
    msg = (
        "*Learning Stats*\n\n"
        f"Words: {stats['total_words']}\n"
        f"Due reviews: {stats['due_reviews']}\n"
        f"Reviews today: {stats['reviews_today']}\n"
        f"Total reviews: {stats['total_reviews']}\n"
        f"Maturing words: {stats['maturing_words']}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())
    log_openclaw_step("stats", 3, 3, "Send stats to Telegram")


@router.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, bot)
        await dispatch_update(update)
        return {"ok": True}
    except Exception as error:
        print(f"[Webhook Error] {error}")
        return {"ok": True}


async def dispatch_update(update: Update):
    if update.message and update.message.text:
        await handle_text(update, None)
    elif update.callback_query:
        await handle_callback(update, None)


async def poll_telegram_updates(stop_event: asyncio.Event):
    offset = None
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        print("Telegram polling enabled. Webhook disabled for local development.")
    except Exception as error:
        print(f"Could not delete Telegram webhook before polling: {error}")

    while not stop_event.is_set():
        try:
            updates = await bot.get_updates(
                offset=offset,
                timeout=20,
                allowed_updates=["message", "callback_query"],
            )
            for update in updates:
                offset = update.update_id + 1
                await dispatch_update(update)
        except Exception as error:
            print(f"[Polling Error] {error}")
            await asyncio.sleep(3)


async def set_webhook():
    webhook_url = f"{settings.WEBHOOK_URL}/telegram/webhook"
    try:
        await bot.set_webhook(url=webhook_url)
        print(f"Webhook set: {webhook_url}")
    except Exception as error:
        print(f"Webhook failed: {error}")
        print("For local testing set TELEGRAM_DELIVERY=polling. For deployment use a public HTTPS WEBHOOK_URL.")
