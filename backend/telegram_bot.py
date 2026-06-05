from fastapi import APIRouter, Request, HTTPException
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
import json

from backend.config import settings
from backend.database import get_or_create_user, get_words, get_word_by_name, get_due_reviews, delete_word
from backend.agent import ExampleSearchAgent

router = APIRouter(prefix="/telegram")
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

# Simple in-memory state storage (resets on redeploy, but works for demo)
user_states = {}

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add Word", callback_data="menu_add")],
        [InlineKeyboardButton("🔍 Query Word", callback_data="menu_query"),
         InlineKeyboardButton("📚 My List", callback_data="menu_list")],
        [InlineKeyboardButton("🔄 Review", callback_data="menu_review"),
         InlineKeyboardButton("🎯 Quiz", callback_data="menu_quiz")]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_keyboard():
    keyboard = [[InlineKeyboardButton("← Back to Menu", callback_data="menu_main")]]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context=None):
    welcome = """📚 *AI Vocabulary Assistant*

Learn English words with *real news examples*!

Choose an option below:"""
    await update.message.reply_text(
        welcome, 
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard()
    )

async def handle_callback(update: Update, context=None):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = get_or_create_user(
        telegram_id=str(update.effective_user.id),
        username=update.effective_user.username
    )
    user_id = user["id"]
    telegram_id = str(update.effective_user.id)
    
    if data == "menu_main":
        try:
            await query.edit_message_text(
                "📚 *Main Menu*\n\nChoose an option:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard()
            )
        except:
            await query.message.reply_text(
                "📚 *Main Menu*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard()
            )
    
    elif data == "menu_add":
        user_states[telegram_id] = "waiting_for_word_to_add"
        try:
            await query.edit_message_text(
                "➕ *Add Word*\n\nType the word you want to add:\n\nExample: `economy`, `sanction`, `abandon`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_keyboard()
            )
        except:
            await query.message.reply_text(
                "➕ *Add Word*\n\nType the word:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_keyboard()
            )
    
    elif data == "menu_query":
        user_states[telegram_id] = "waiting_for_word_to_query"
        try:
            await query.edit_message_text(
                "🔍 *Query Word*\n\nType the word you want to look up:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_keyboard()
            )
        except:
            await query.message.reply_text(
                "🔍 *Query Word*\n\nType the word:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_keyboard()
            )
    
    elif data == "menu_list":
        await show_list(query, user_id, edit=True)
    
    elif data == "menu_review":
        await show_review(query, user_id, edit=True)
    
    elif data == "menu_quiz":
        await show_quiz(query, user_id, edit=True)
    
    elif data.startswith("know_"):
        word_id = int(data.split("_")[1])
        await handle_review_result(query, word_id, user_id, known=True)
    
    elif data.startswith("dontknow_"):
        word_id = int(data.split("_")[1])
        await handle_review_result(query, word_id, user_id, known=False)
    
    elif data.startswith("delete_"):
        word_id = int(data.split("_")[1])
        await handle_delete(query, word_id, user_id)

async def show_list(query, user_id, edit=False):
    words = get_words(user_id, limit=20)
    
    if not words:
        msg = "📭 Your vocabulary is empty!\n\nClick ➕ *Add Word* to start."
    else:
        msg = "📚 *Your Vocabulary* (last 20)\n\n"
        for i, w in enumerate(words, 1):
            msg += f"{i}. *{w['word']}* — {w['chinese_meaning']}\n"
    
    if edit:
        try:
            await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())
        except:
            await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())
    else:
        await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())

async def show_review(query, user_id, edit=False):
    due = get_due_reviews(user_id)
    
    if not due:
        msg = "🎉 *No words due for review!*\n\nYou're all caught up. Great job!"
        if edit:
            try:
                await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())
            except:
                await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())
        else:
            await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())
        return
    
    word = due[0]
    keyboard = [
        [InlineKeyboardButton("❌ Again", callback_data=f"dontknow_{word['id']}"),
         InlineKeyboardButton("✅ Good", callback_data=f"know_{word['id']}")]
    ]
    
    msg = f"""🔄 *Review Time!* ({len(due)} words due)

📖 *{word['word']}* `{word['phonetic']}`

📝 {word['example_sentence']}

Do you remember the meaning?"""
    
    if edit:
        try:
            await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_review_result(query, word_id, user_id, known):
    from backend.database import update_review
    quality = 4 if known else 1
    update_review(word_id, user_id, quality)
    
    if known:
        await query.answer("✅ Marked as known!")
    else:
        await query.answer("❌ Will review again soon!")
    
    await show_review(query, user_id, edit=False)

async def show_quiz(query, user_id, edit=False):
    import random
    words = get_words(user_id, limit=50)
    
    if len(words) < 4:
        msg = "❌ Need at least 4 words for a quiz!\n\nAdd more words first."
        if edit:
            try:
                await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())
            except:
                await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())
        else:
            await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())
        return
    
    target = random.choice(words)
    distractors = random.sample([w for w in words if w["id"] != target["id"]], 3)
    options = [target] + distractors
    random.shuffle(options)
    
    correct_idx = next(i for i, o in enumerate(options) if o["id"] == target["id"])
    
    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(f"{chr(65+i)}. {opt['chinese_meaning']}", callback_data=f"quiz_{target['id']}_{i}_{correct_idx}")])
    
    msg = f"""🎯 *Quiz!*

What does *{target['word']}* mean?"""
    
    if edit:
        try:
            await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_delete(query, word_id, user_id):
    delete_word(word_id, user_id)
    await query.answer("🗑️ Word deleted!")
    try:
        await query.edit_message_text("✅ Word deleted successfully!", reply_markup=main_menu_keyboard())
    except:
        await query.message.reply_text("✅ Word deleted successfully!", reply_markup=main_menu_keyboard())

async def handle_text(update: Update, context=None):
    text = update.message.text.strip().lower()
    user = get_or_create_user(
        telegram_id=str(update.effective_user.id),
        username=update.effective_user.username
    )
    user_id = user["id"]
    telegram_id = str(update.effective_user.id)
    
    state = user_states.get(telegram_id, "")
    
    if state == "waiting_for_word_to_add":
        user_states[telegram_id] = ""
        await add_word_flow(update, text, user_id)
    
    elif state == "waiting_for_word_to_query":
        user_states[telegram_id] = ""
        await query_word_flow(update, text, user_id)
    
    else:
        # Default: treat as add word
        await add_word_flow(update, text, user_id)

async def add_word_flow(update, word, user_id):
    loading_msg = await update.message.reply_text(f"⏳ Searching real news for *{word}*...", parse_mode=ParseMode.MARKDOWN)
    
    try:
        agent = ExampleSearchAgent()
        result = await agent.execute(word, user_id=user_id)
        
        if result.get("status") == "exists":
            await loading_msg.edit_text(
                f"⚠️ *{result['word']}* already exists!\n\n📝 {result['example']}\n🇨🇳 {result['translation']}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard()
            )
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
        
        await loading_msg.edit_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
            reply_markup=main_menu_keyboard()
        )
        
    except ValueError as e:
        await loading_msg.edit_text(f"❌ {str(e)}", reply_markup=main_menu_keyboard())
    except Exception as e:
        print(f"[Add Error] {e}")
        await loading_msg.edit_text("❌ Error searching for word. Try again.", reply_markup=main_menu_keyboard())

async def query_word_flow(update, word, user_id):
    result = get_word_by_name(word.lower(), user_id)
    
    if not result:
        await update.message.reply_text(
            f"🔍 *{word}* not found.\n\nClick ➕ *Add Word* to add it.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard()
        )
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
    
    keyboard = [
        [InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_{result['id']}"),
         InlineKeyboardButton("← Back", callback_data="menu_main")]
    ]
    
    await update.message.reply_text(
        msg,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@router.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, bot)
        
        if update.message:
            if update.message.text:
                text = update.message.text.strip()
                
                if text.startswith("/start"):
                    await start_command(update, None)
                else:
                    await handle_text(update, None)
        
        elif update.callback_query:
            await handle_callback(update, None)
        
        return {"ok": True}
        
    except Exception as e:
        print(f"[Webhook Error] {e}")
        return {"ok": True}  # Don't return 500 to Telegram

async def set_webhook():
    webhook_url = f"{settings.WEBHOOK_URL}/telegram/webhook"
    try:
        await bot.set_webhook(url=webhook_url)
        print(f"✅ Webhook set: {webhook_url}")
    except Exception as e:
        print(f"❌ Webhook failed: {e}")