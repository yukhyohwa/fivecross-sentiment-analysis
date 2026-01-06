import sqlite3
import datetime

import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.path.join(BASE_DIR, 'data', 'jump_reviews.db')

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id TEXT PRIMARY KEY,
            game_id TEXT,
            author TEXT,
            rating INTEGER,
            content TEXT,
            review_date TEXT,
            sentiment_score REAL,
            sentiment_label TEXT,
            character_mentions TEXT,
            detailed_analysis TEXT,
            crawled_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def migrate_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE reviews ADD COLUMN detailed_analysis TEXT")
    except: pass
    try:
        c.execute("ALTER TABLE reviews ADD COLUMN game_id TEXT")
    except: pass
    conn.commit()
    conn.close()

def save_review(review_data):
    """
    review_data: dict with id, game_id, author, rating, content, date
    """
    migrate_db() # Ensure column exists
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute('''
            INSERT OR IGNORE INTO reviews (id, game_id, author, rating, content, review_date, crawled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            review_data['id'],
            review_data.get('game_id', 'jump_assemble'), # Default fallback
            review_data['author'],
            review_data['rating'],
            review_data['content'],
            review_data['date'],
            datetime.datetime.now().isoformat()
        ))
        conn.commit()
    except Exception as e:
        print(f"Error saving review: {e}")
    finally:
        conn.close()

def get_reviews_for_analysis(game_id=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        sql = "SELECT id, content, game_id FROM reviews WHERE detailed_analysis IS NULL"
        if game_id:
            sql += f" AND game_id = '{game_id}'"
        c.execute(sql)
    except:
        migrate_db()
        return []
        
    rows = c.fetchall()
    conn.close()
    return rows

def update_analysis_results(review_id, sentiment_score, sentiment_label, character_mentions, detailed_analysis=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        UPDATE reviews
        SET sentiment_score = ?, sentiment_label = ?, character_mentions = ?, detailed_analysis = ?
        WHERE id = ?
    ''', (sentiment_score, sentiment_label, character_mentions, detailed_analysis, review_id))
    conn.commit()
    conn.close()

def get_all_data():
    conn = sqlite3.connect(DB_NAME)
    import pandas as pd
    df = pd.read_sql_query("SELECT * FROM reviews", conn)
    conn.close()
    return df
