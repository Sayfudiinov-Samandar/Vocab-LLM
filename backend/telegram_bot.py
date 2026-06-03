from fastapi import APIRouter, Request, HTTPException
from telegram import Update, Bot
from telegram.constants import ParseMode
import json

from .config import settings
from .database import get_or_create_user, get_words, get_word_by_name, get_due_reviews, delete_word
from .agent import ExampleSearchAgent

router = APIRouter(prefix="/telegram")
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

async def start_command(update: Update, context):
    welcome = """📚 *AI Vocabulary Assistant*

I help you learn English with *real news examples*.

*Commands:*
/add `<word>` — Add word (searches real news)
/query `<word>` — Look up saved word
/review — Review due words
/quiz — Quick quiz
/list — List vocabulary
/delete `<word>` — Remove word

Try: `/add sanction`"""
    await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN)

async def add_command(update: Update, context):
    word = context.args[0] if context.args else None
    if not word:
        await update.message.reply_text("❌ Usage: `/add <word>`", parse_mode=ParseMode.MARKDOWN)
        return
    
    await update.message.chat.send_action(action="typing")
    
    user = get_or_create_user(
        telegram_id=str(update.effective_user.id),
        username=update.effective_user.username
    )
    
    try:
        agent = ExampleSearchAgent()
        result = await agent.execute(word, user_id=user["id"])
        
        if result.get("status") == "exists":
            msg = f"""⚠️ *{result['word']}* already exists!

📝 {result['example']}
🇨🇳 {result['translation']}
🔗 [Source: {result['source']}]({result['url']})"""
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
            return
        
        collocations = "\n".join([f"• {c}" for c in result.get("collocations", [])])
        synonyms = ", ".join(result.get("synonyms", []))
        antonyms = ", ".join(result.get("antonyms", []))
        
        msg = f"""✅ *Word Added!*

📖 *{result['word']}* `{result['phonetic']}` *{result['pos']}*
💡 {result['meaning']}

📝 *Example:*
_{result['example']}_

🇨🇳 *Translation:*
{result['translation']}

🔗 *Source:* [{result['source']}]({result['url']})

📌 *Collocations:*
{collocations}

🔄 *Synonyms:* {synonyms}
➡️ *Antonyms:* {antonyms}"""
        
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        
    except ValueError as e:
        await update.message.reply_text(f"❌ {str(e)}")
    except Exception as e:
        print(f"[Add Error] {e}")
        await update.message.reply_text("❌ Error searching for word. Try again.")

async def query_command(update: Update, context):
    word = context.args[0] if context.args else None
    if not word:
        await update.message.reply_text("❌ Usage: `/query <word>`", parse_mode=ParseMode.MARKDOWN)
        return
    
    user = get_or_create_user(telegram_id=str(update.effective_user.id))
    result = get_word_by_name(word.lower(), user["id"])
    
    if not result:
        await update.message.reply_text(f"🔍 '{word}' not found. Use `/add {word}` to add it.", parse_mode=ParseMode.MARKDOWN)
        return
    
    import json
    collocations = "\n".join([f"• {c}" for c in json.loads(result.get("collocations", "[]"))])
    
    msg = f"""📖 *{result['word']}* `{result['phonetic']}` *{result['part_of_speech']}*
💡 {result['chinese_meaning']}

📝 *Example:*
_{result['example_sentence']}_

🇨🇳 {result['chinese_translation']}

🔗 [Source: {result['source_name']}]({result['source_url']})

📌 *Collocations:*
{collocations}"""
    
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

async def list_command(update: Update, context):
    user = get_or_create_user(telegram_id=str(update.effective_user.id))
    words = get_words(user_id=user["id"], limit=20)
    
    if not words:
        await update.message.reply_text("📭 Empty. Use `/add <word>` to start.", parse_mode=ParseMode.MARKDOWN)
        return
    
    msg = "📚 *Your Vocabulary* (last 20)\n\n"
    for i, w in enumerate(words, 1):
        msg += f"{i}. *{w['word']}* — {w['chinese_meaning']}\n"
    
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def review_command(update: Update, context):
    user = get_or_create_user(telegram_id=str(update.effective_user.id))
    due = get_due_reviews(user_id=user["id"])
    
    if not due:
        await update.message.reply_text("🎉 No words due! You're all caught up.")
        return
    
    word = due[0]
    msg = f"""🔄 *Review!* ({len(due)} words due)

📖 *{word['word']}* `{word['phonetic']}`

📝 {word['example_sentence']}

Do you remember the meaning?"""
    
    await update.message.reply_text(
        msg + f"\n\nReply: `/know {word['word']}` or `/dontknow {word['word']}`",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

async def quiz_command(update: Update, context):
    user = get_or_create_user(telegram_id=str(update.effective_user.id))
    words = get_words(user_id=user["id"], limit=50)
    
    if len(words) < 4:
        await update.message.reply_text("❌ Need at least 4 words for a quiz. Add more!")
        return
    
    import random
    target = random.choice(words)
    distractors = random.sample([w for w in words if w["id"] != target["id"]], 3)
    options = [target] + distractors
    random.shuffle(options)
    
    correct_idx = next(i for i, o in enumerate(options) if o["id"] == target["id"])
    
    msg = f"""🎯 *Quiz!*

What does *{target['word']}* mean?

"""
    for i, opt in enumerate(options):
        msg += f"{chr(65+i)}. {opt['chinese_meaning']}\n"
    
    msg += f"\nReply with A, B, C, or D.\n(Answer: {chr(65+correct_idx)})"
    
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def delete_command(update: Update, context):
    word = context.args[0] if context.args else None
    if not word:
        await update.message.reply_text("❌ Usage: `/delete <word>`", parse_mode=ParseMode.MARKDOWN)
        return
    
    user = get_or_create_user(telegram_id=str(update.effective_user.id))
    w = get_word_by_name(word.lower(), user["id"])
    
    if not w:
        await update.message.reply_text(f"❌ '{word}' not found.")
        return
    
    deleted = delete_word(w["id"], user["id"])
    if deleted:
        await update.message.reply_text(f"🗑️ '{word}' deleted.")
    else:
        await update.message.reply_text(f"❌ Could not delete '{word}'.")

@router.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, bot)
        
        if not update.message or not update.message.text:
            return {"ok": True}
        
        text = update.message.text.strip()
        
        class FakeContext:
            pass
        
        ctx = FakeContext()
        ctx.args = text.split()[1:] if len(text.split()) > 1 else []
        
        if text.startswith("/start"):
            await start_command(update, ctx)
        elif text.startswith("/add "):
            await add_command(update, ctx)
        elif text.startswith("/query "):
            await query_command(update, ctx)
        elif text.startswith("/list"):
            await list_command(update, ctx)
        elif text.startswith("/review"):
            await review_command(update, ctx)
        elif text.startswith("/quiz"):
            await quiz_command(update, ctx)
        elif text.startswith("/delete "):
            await delete_command(update, ctx)
        else:
            await update.message.reply_text(
                "🤖 Try: `/add sanction`, `/query sanction`, `/review`, or `/quiz`",
                parse_mode=ParseMode.MARKDOWN
            )
        
        return {"ok": True}
        
    except Exception as e:
        print(f"[Webhook Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def set_webhook():
    webhook_url = f"{settings.WEBHOOK_URL}/telegram/webhook"
    try:
        await bot.set_webhook(url=webhook_url)
        print(f"✅ Webhook set: {webhook_url}")
    except Exception as e:
        print(f"❌ Webhook failed: {e}")