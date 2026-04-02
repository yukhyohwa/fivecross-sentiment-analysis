import sqlite3
import datetime

import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.path.join(BASE_DIR, 'data', 'jump_reviews.db')
CHAT_DB_NAME = os.path.join(BASE_DIR, 'data', 'jump_chats.db')

def init_db():
    # 1. Platform Reviews DB
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
            source TEXT,
            content_title TEXT,
            content_url TEXT,
            original_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

    # 2. Chat / Community DB
    chat_conn = sqlite3.connect(CHAT_DB_NAME)
    cc = chat_conn.cursor()
    cc.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            game_id TEXT,
            channel TEXT,
            author TEXT,
            content TEXT,
            message_date TEXT,
            source TEXT,
            sentiment_score REAL,
            sentiment_label TEXT,
            character_mentions TEXT,
            detailed_analysis TEXT,
            crawled_at TEXT,
            embedding BLOB,
            x REAL,
            y REAL,
            cluster_label TEXT
        )
    ''')
    chat_conn.commit()
    chat_conn.close()

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
    try: c.execute("ALTER TABLE reviews ADD COLUMN original_date TEXT")
    except: pass
    
    # Standardized Columns
    try: c.execute("ALTER TABLE reviews ADD COLUMN content_title TEXT")
    except: pass
    try: c.execute("ALTER TABLE reviews ADD COLUMN content_url TEXT")
    except: pass
    
    # Semantic Map Columns
    try: c.execute("ALTER TABLE reviews ADD COLUMN embedding BLOB")
    except: pass
    try: c.execute("ALTER TABLE reviews ADD COLUMN x REAL")
    except: pass
    try: c.execute("ALTER TABLE reviews ADD COLUMN y REAL")
    except: pass
    try: c.execute("ALTER TABLE reviews ADD COLUMN cluster_label TEXT")
    except: pass
        
    conn.commit()
    conn.close()

def save_review(review_data):
    """
    review_data: dict with id, game_id, author, rating, content, date, source, 
                 content_title, content_url, original_date
    """
    migrate_db() # Ensure connection/schema
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    try:
        c.execute('''
            INSERT OR IGNORE INTO reviews (
                id, game_id, author, rating, content, review_date, crawled_at, source, 
                content_title, content_url, original_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            review_data['id'],
            review_data.get('game_id', 'jump_assemble'),
            review_data.get('author', 'Anonymous'),
            review_data.get('rating', 0),
            review_data['content'],
            review_data.get('date', datetime.datetime.now().strftime('%Y-%m-%d')),
            datetime.datetime.now().isoformat(),
            review_data.get('source', 'unknown'),
            review_data.get('content_title', ''),
            review_data.get('content_url', ''),
            review_data.get('original_date', '')
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
        sql = "SELECT id, content, game_id, source, review_date FROM reviews"
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

def save_chat_message(msg_data):
    """
    msg_data: dict with id, game_id, channel, author, content, message_date, source
    """
    conn = sqlite3.connect(CHAT_DB_NAME)
    c = conn.cursor()
    try:
        c.execute('''
            INSERT OR IGNORE INTO chat_messages (
                id, game_id, channel, author, content, message_date, source, crawled_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            msg_data['id'],
            msg_data.get('game_id', 'jump_assemble'),
            msg_data.get('channel', 'unknown'),
            msg_data.get('author', 'Anonymous'),
            msg_data['content'],
            msg_data['message_date'],
            msg_data.get('source', 'discord_chat'),
            datetime.datetime.now().isoformat()
        ))
        conn.commit()
    except Exception as e:
        print(f"Error saving chat message: {e}")
    finally:
        conn.close()

def get_chats_for_analysis(game_id=None, force=False):
    conn = sqlite3.connect(CHAT_DB_NAME)
    c = conn.cursor()
    try:
        sql = "SELECT id, content, game_id, source, message_date FROM chat_messages"
        conditions = []
        if not force:
            conditions.append("detailed_analysis IS NULL")
        if game_id:
            conditions.append(f"game_id = '{game_id}'")
        
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        c.execute(sql)
        rows = c.fetchall()
        return rows
    finally:
        conn.close()

def update_chat_analysis(msg_id, sentiment_score, sentiment_label, character_mentions, detailed_analysis=None):
    conn = sqlite3.connect(CHAT_DB_NAME)
    c = conn.cursor()
    c.execute('''
        UPDATE chat_messages
        SET sentiment_score = ?, sentiment_label = ?, character_mentions = ?, detailed_analysis = ?
        WHERE id = ?
    ''', (sentiment_score, sentiment_label, character_mentions, detailed_analysis, msg_id))
    conn.commit()
    conn.close()

def get_all_data():
    import pandas as pd
    
    # 1. Fetch Reviews
    conn_r = sqlite3.connect(DB_NAME)
    try:
        df_r = pd.read_sql_query("SELECT * FROM reviews", conn_r)
    except:
        df_r = pd.DataFrame()
    conn_r.close()
    
    # 2. Fetch Chats
    conn_c = sqlite3.connect(CHAT_DB_NAME)
    try:
        df_c = pd.read_sql_query("SELECT * FROM chat_messages", conn_c)
        if not df_c.empty:
            # Align columns for seamless display
            # Rename message_date to review_date so time-series charts work automatically
            df_c = df_c.rename(columns={'message_date': 'review_date'})
            # Add missing rating column (filled with None/0 for chats)
            if 'rating' not in df_c.columns:
                df_c['rating'] = 0
    except:
        df_c = pd.DataFrame()
    conn_c.close()
    
    # 3. Concatenate
    if df_r.empty: return df_c
    if df_c.empty: return df_r
    
    return pd.concat([df_r, df_c], ignore_index=True, sort=False)

def get_all_chats():
    conn = sqlite3.connect(CHAT_DB_NAME)
    import pandas as pd
    try:
        df = pd.read_sql_query("SELECT * FROM chat_messages", conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df
