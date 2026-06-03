import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

DB_PATH = "vocab.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id TEXT UNIQUE,
            username TEXT,
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
            example_sentence TEXT NOT NULL,
            chinese_translation TEXT,
            source_name TEXT,
            source_url TEXT NOT NULL,
            collocations TEXT,
            synonyms TEXT,
            antonyms TEXT,
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
        (user_id, word, phonetic, part_of_speech, chinese_meaning, example_sentence,
         chinese_translation, source_name, source_url, collocations, synonyms, antonyms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record["user_id"],
        record["word"],
        record.get("phonetic", ""),
        record.get("part_of_speech", ""),
        record.get("chinese_meaning", ""),
        record["example_sentence"],
        record.get("chinese_translation", ""),
        record.get("source_name", ""),
        record["source_url"],
        record.get("collocations", "[]"),
        record.get("synonyms", "[]"),
        record.get("antonyms", "[]")
    ))
    
    word_id = cursor.lastrowid
    
    cursor.execute("""
        INSERT INTO reviews (word_id, user_id, next_review)
        VALUES (?, ?, ?)
    """, (word_id, record["user_id"], datetime.now().date()))
    
    conn.commit()
    conn.close()
    return word_id

def get_words(user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
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

def delete_word(word_id: int, user_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
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
    
    conn.commit()
    conn.close()