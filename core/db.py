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
            crawled_at TEXT,
            source TEXT
        )
    ''')
    conn.commit()
    conn.close()

def migrate_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Existing Migrations
    try: c.execute("ALTER TABLE reviews ADD COLUMN detailed_analysis TEXT")
    except: pass
    try: c.execute("ALTER TABLE reviews ADD COLUMN game_id TEXT")
    except: pass
    try: c.execute("ALTER TABLE reviews ADD COLUMN source TEXT")
    except: pass
    try: c.execute("ALTER TABLE reviews ADD COLUMN video_title TEXT")
    except: pass
    try: c.execute("ALTER TABLE reviews ADD COLUMN video_url TEXT")
    except: pass
    try: c.execute("ALTER TABLE reviews ADD COLUMN original_date TEXT")
    except: pass
    
    # New Standardized Columns (Step Id 857)
    try: 
        c.execute("ALTER TABLE reviews ADD COLUMN content_title TEXT")
        # Backfill from video_title if empty
        c.execute("UPDATE reviews SET content_title = video_title WHERE content_title IS NULL AND video_title IS NOT NULL")
    except: pass
    
    try: 
        c.execute("ALTER TABLE reviews ADD COLUMN content_url TEXT")
        # Backfill from video_url if empty
        c.execute("UPDATE reviews SET content_url = video_url WHERE content_url IS NULL AND video_url IS NOT NULL")
    except: pass
        
    conn.commit()
    conn.close()

def save_review(review_data):
    """
    review_data: dict with id, game_id, author, rating, content, date, source, 
                 content_title (was video_title), content_url (was video_url), original_date
    """
    migrate_db() # Ensure connection/schema
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Normalize keys: support both old 'video_' and new 'content_' keys
    c_title = review_data.get('content_title') or review_data.get('video_title') or ''
    c_url = review_data.get('content_url') or review_data.get('video_url') or ''
    
    try:
        c.execute('''
            INSERT OR IGNORE INTO reviews (
                id, game_id, author, rating, content, review_date, crawled_at, source, 
                content_title, content_url, original_date,
                video_title, video_url 
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            review_data['id'],
            review_data.get('game_id', 'jump_assemble'),
            review_data.get('author', 'Anonymous'),
            review_data.get('rating', 0),
            review_data['content'],
            review_data.get('date', datetime.datetime.now().strftime('%Y-%m-%d')),
            datetime.datetime.now().isoformat(),
            review_data.get('source', 'unknown'),
            c_title,
            c_url,
            review_data.get('original_date', ''),
            c_title, # Keep filling old columns for safety
            c_url
        ))
        conn.commit()
    except Exception as e:
        print(f"Error saving review: {e}")
    finally:
        conn.close()


def get_reviews_for_analysis(game_id=None, force=False):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        sql = "SELECT id, content, game_id FROM reviews"
        conditions = []
        if not force:
            conditions.append("detailed_analysis IS NULL")
        if game_id:
            conditions.append(f"game_id = '{game_id}'")
        
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
            
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
