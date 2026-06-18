import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

DEFAULT_DB_PATH = os.path.join("data", "vocab.db")


def get_db_path() -> str:
    database_url = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")
    if database_url.startswith("sqlite:///"):
        parsed = urlparse(database_url)
        if parsed.path:
            return parsed.path.lstrip("/") if not parsed.path.startswith("//") else parsed.path
        return database_url.replace("sqlite:///", "", 1)
    return DEFAULT_DB_PATH

def get_db_connection():
    db_path = get_db_path()
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _add_column_if_missing(cursor: sqlite3.Cursor, table: str, column: str, definition: str):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in cursor.fetchall()}
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _record_learning_event(
    cursor: sqlite3.Cursor,
    user_id: int,
    event_type: str,
    word_id: Optional[int] = None,
    word_text: Optional[str] = None,
    detail: str = "",
):
    cursor.execute(
        """
        INSERT INTO learning_records (user_id, word_id, word_text, event_type, detail)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, word_id, word_text, event_type, detail),
    )

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id TEXT UNIQUE,
            username TEXT,
            reminder_enabled INTEGER DEFAULT 0,
            reminder_time TEXT DEFAULT '08:00',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vocabulary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            word TEXT NOT NULL,
            phonetic TEXT,
            part_of_speech TEXT,
            chinese_meaning TEXT,
            english_definition TEXT,
            example_sentence TEXT NOT NULL,
            chinese_translation TEXT,
            source_name TEXT,
            source_url TEXT NOT NULL,
            source_type TEXT DEFAULT 'authentic',
            collocations TEXT,
            synonyms TEXT,
            antonyms TEXT,
            memory_tip TEXT,
            difficulty INTEGER DEFAULT 2,
            favorite INTEGER DEFAULT 0,
            tags TEXT DEFAULT '[]',
            audio_url TEXT,
            notes TEXT,
            updated_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            ease_factor REAL DEFAULT 2.5,
            interval_days INTEGER DEFAULT 1,
            next_review DATE,
            review_count INTEGER DEFAULT 0,
            FOREIGN KEY (word_id) REFERENCES vocabulary(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS review_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            quality INTEGER NOT NULL,
            known INTEGER NOT NULL,
            interval_days INTEGER,
            ease_factor REAL,
            next_review DATE,
            reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (word_id) REFERENCES vocabulary(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            word_id INTEGER,
            word_text TEXT,
            event_type TEXT NOT NULL,
            detail TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    _add_column_if_missing(cursor, "users", "reminder_enabled", "INTEGER DEFAULT 0")
    _add_column_if_missing(cursor, "users", "reminder_time", "TEXT DEFAULT '08:00'")
    _add_column_if_missing(cursor, "vocabulary", "english_definition", "TEXT")
    _add_column_if_missing(cursor, "vocabulary", "source_type", "TEXT DEFAULT 'authentic'")
    _add_column_if_missing(cursor, "vocabulary", "memory_tip", "TEXT")
    _add_column_if_missing(cursor, "vocabulary", "difficulty", "INTEGER DEFAULT 2")
    _add_column_if_missing(cursor, "vocabulary", "favorite", "INTEGER DEFAULT 0")
    _add_column_if_missing(cursor, "vocabulary", "tags", "TEXT DEFAULT '[]'")
    _add_column_if_missing(cursor, "vocabulary", "audio_url", "TEXT")
    _add_column_if_missing(cursor, "vocabulary", "notes", "TEXT")
    _add_column_if_missing(cursor, "vocabulary", "updated_at", "TIMESTAMP")
    
    conn.commit()
    conn.close()

def get_or_create_user(telegram_id: Optional[str] = None, username: Optional[str] = None) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if telegram_id:
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        user = cursor.fetchone()
        if user:
            conn.close()
            return dict(user)
    
    cursor.execute(
        "INSERT INTO users (telegram_id, username) VALUES (?, ?)",
        (telegram_id, username)
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return {"id": user_id, "telegram_id": telegram_id, "username": username}

def save_word(record: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO vocabulary 
        (user_id, word, phonetic, part_of_speech, chinese_meaning, english_definition,
         example_sentence, chinese_translation, source_name, source_url, source_type,
         collocations, synonyms, antonyms, memory_tip, difficulty, favorite,
         tags, audio_url, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record["user_id"],
        record["word"].lower().strip(),
        record.get("phonetic", ""),
        record.get("part_of_speech", ""),
        record.get("chinese_meaning", ""),
        record.get("english_definition", ""),
        record["example_sentence"],
        record.get("chinese_translation", ""),
        record.get("source_name", ""),
        record["source_url"],
        record.get("source_type", "authentic"),
        record.get("collocations", "[]"),
        record.get("synonyms", "[]"),
        record.get("antonyms", "[]"),
        record.get("memory_tip", ""),
        record.get("difficulty", 2),
        record.get("favorite", 0),
        record.get("tags", "[]"),
        record.get("audio_url", ""),
        record.get("notes", "")
    ))
    
    word_id = cursor.lastrowid
    
    cursor.execute("""
        INSERT INTO reviews (word_id, user_id, next_review)
        VALUES (?, ?, ?)
    """, (word_id, record["user_id"], datetime.now().date()))

    _record_learning_event(
        cursor,
        record["user_id"],
        "created",
        word_id=word_id,
        word_text=record["word"].lower().strip(),
        detail="Added by Example Search Agent",
    )
    
    conn.commit()
    conn.close()
    return word_id

def get_words(user_id: int, limit: int = 100, q: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if q:
        pattern = f"%{q.lower().strip()}%"
        cursor.execute("""
            SELECT * FROM vocabulary
            WHERE user_id = ?
              AND (
                lower(word) LIKE ?
                OR lower(chinese_meaning) LIKE ?
                OR lower(tags) LIKE ?
              )
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, pattern, pattern, pattern, limit))
    else:
        cursor.execute("""
            SELECT * FROM vocabulary WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
        """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_word_by_id(word_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vocabulary WHERE id = ?", (word_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_word_by_name(word: str, user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vocabulary WHERE word = ? AND user_id = ?", (word.lower(), user_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_word(word_id: int, user_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed_fields = {
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
        "collocations",
        "synonyms",
        "antonyms",
        "memory_tip",
        "difficulty",
        "favorite",
        "tags",
        "audio_url",
        "notes",
    }
    clean_updates = {
        field: value
        for field, value in updates.items()
        if field in allowed_fields and value is not None
    }

    if "word" in clean_updates:
        clean_updates["word"] = str(clean_updates["word"]).lower().strip()

    if not clean_updates:
        return get_word_by_id(word_id)

    clean_updates["updated_at"] = datetime.now()
    assignments = ", ".join([f"{field} = ?" for field in clean_updates])
    values = list(clean_updates.values()) + [word_id, user_id]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE vocabulary SET {assignments} WHERE id = ? AND user_id = ?",
        values,
    )
    if cursor.rowcount == 0:
        conn.close()
        return None

    cursor.execute("SELECT word FROM vocabulary WHERE id = ?", (word_id,))
    row = cursor.fetchone()
    _record_learning_event(
        cursor,
        user_id,
        "updated",
        word_id=word_id,
        word_text=row["word"] if row else None,
        detail=", ".join(clean_updates.keys()),
    )
    conn.commit()
    conn.close()
    return get_word_by_id(word_id)

def delete_word(word_id: int, user_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT word FROM vocabulary WHERE id = ? AND user_id = ?", (word_id, user_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    cursor.execute("DELETE FROM reviews WHERE word_id = ? AND user_id = ?", (word_id, user_id))
    cursor.execute("DELETE FROM review_history WHERE word_id = ? AND user_id = ?", (word_id, user_id))
    _record_learning_event(
        cursor,
        user_id,
        "deleted",
        word_id=None,
        word_text=row["word"],
        detail=f"Deleted word id {word_id}",
    )
    cursor.execute("DELETE FROM vocabulary WHERE id = ? AND user_id = ?", (word_id, user_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_due_reviews(user_id: int) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.*, r.ease_factor, r.interval_days, r.review_count
        FROM vocabulary v
        JOIN reviews r ON v.id = r.word_id
        WHERE v.user_id = ? AND r.next_review <= ?
        ORDER BY r.next_review ASC
        LIMIT 10
    """, (user_id, datetime.now().date()))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_review(word_id: int, user_id: int, quality: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM reviews WHERE word_id = ? AND user_id = ?", (word_id, user_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return
    
    review = dict(row)
    ease_factor = review["ease_factor"]
    interval = review["interval_days"]
    count = review["review_count"]
    
    if quality >= 3:
        if count == 0:
            interval = 1
        elif count == 1:
            interval = 6
        else:
            interval = int(interval * ease_factor)
    else:
        interval = 1
    
    ease_factor = max(1.3, ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    
    next_review = datetime.now().date() + timedelta(days=interval)
    
    cursor.execute("""
        UPDATE reviews 
        SET ease_factor = ?, interval_days = ?, next_review = ?, review_count = ?
        WHERE word_id = ? AND user_id = ?
    """, (ease_factor, interval, next_review, count + 1, word_id, user_id))

    cursor.execute("""
        INSERT INTO review_history
        (word_id, user_id, quality, known, interval_days, ease_factor, next_review)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (word_id, user_id, quality, 1 if quality >= 3 else 0, interval, ease_factor, next_review))

    cursor.execute("SELECT word FROM vocabulary WHERE id = ?", (word_id,))
    word_row = cursor.fetchone()
    _record_learning_event(
        cursor,
        user_id,
        "reviewed",
        word_id=word_id,
        word_text=word_row["word"] if word_row else None,
        detail=f"quality={quality}; next_review={next_review}",
    )
    
    conn.commit()
    conn.close()


def get_review_history(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT h.*, v.word, v.chinese_meaning
        FROM review_history h
        LEFT JOIN vocabulary v ON h.word_id = v.id
        WHERE h.user_id = ?
        ORDER BY h.reviewed_at DESC
        LIMIT ?
    """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_review_words(user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.*, r.ease_factor, r.interval_days, r.review_count, r.next_review
        FROM vocabulary v
        LEFT JOIN reviews r ON v.id = r.word_id AND v.user_id = r.user_id
        WHERE v.user_id = ?
        ORDER BY COALESCE(r.next_review, v.created_at) ASC, v.created_at DESC
        LIMIT ?
    """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_learning_records(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT *
        FROM learning_records
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
    """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_learning_stats(user_id: int) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.now().date()

    cursor.execute("SELECT COUNT(*) FROM vocabulary WHERE user_id = ?", (user_id,))
    total_words = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM reviews
        WHERE user_id = ? AND next_review <= ?
    """, (user_id, today))
    due_reviews = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM reviews
        WHERE user_id = ? AND interval_days >= 6
    """, (user_id,))
    learning_streak_candidates = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM review_history
        WHERE user_id = ?
    """, (user_id,))
    total_reviews = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM review_history
        WHERE user_id = ? AND date(reviewed_at) = date('now')
    """, (user_id,))
    reviews_today = cursor.fetchone()[0]

    cursor.execute("""
        SELECT tags
        FROM vocabulary
        WHERE user_id = ? AND tags IS NOT NULL AND tags != ''
    """, (user_id,))
    tag_counts: Dict[str, int] = {}
    for row in cursor.fetchall():
        try:
            import json
            tags = json.loads(row["tags"])
        except Exception:
            tags = []
        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    conn.close()
    return {
        "total_words": total_words,
        "due_reviews": due_reviews,
        "maturing_words": learning_streak_candidates,
        "total_reviews": total_reviews,
        "reviews_today": reviews_today,
        "tag_counts": tag_counts,
    }


def get_quiz_question(user_id: int) -> Optional[Dict[str, Any]]:
    words = get_words(user_id, limit=100)
    valid_words = [word for word in words if word.get("chinese_meaning")]
    if len(valid_words) < 4:
        return None

    import random

    target = random.choice(valid_words)
    distractors = random.sample([word for word in valid_words if word["id"] != target["id"]], 3)
    options = [target] + distractors
    random.shuffle(options)
    correct_index = next(index for index, option in enumerate(options) if option["id"] == target["id"])

    return {
        "word_id": target["id"],
        "word": target["word"],
        "phonetic": target.get("phonetic"),
        "example_sentence": target.get("example_sentence"),
        "options": [
            {"index": index, "meaning": option["chinese_meaning"]}
            for index, option in enumerate(options)
        ],
        "correct_index": correct_index,
    }
