import sqlite3
import json
import os

DB_PATH = 'data/jump_reviews.db'

def inspect_db():
    if not os.path.exists(DB_PATH):
        print("DB not found")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Check total
    c.execute("SELECT count(*) as cnt FROM reviews")
    print(f"Total reviews: {c.fetchone()['cnt']}")
    
    # Check for Luffy
    print("\n--- Checking '路飞' ---")
    c.execute("SELECT id, content, detailed_analysis FROM reviews WHERE content LIKE '%路飞%' LIMIT 3")
    rows = c.fetchall()
    if not rows:
        print("No reviews found with '路飞'")
    else:
        for r in rows:
            print(f"Content: {r['content'][:30]}...")
            print(f"Analysis: {r['detailed_analysis']}")
            
    # Check for Robin
    print("\n--- Checking '罗宾' ---")
    c.execute("SELECT id, content, detailed_analysis FROM reviews WHERE content LIKE '%罗宾%' LIMIT 3")
    rows = c.fetchall()
    for r in rows:
        print(f"Content: {r['content'][:30]}...")
        print(f"Analysis: {r['detailed_analysis']}")

    # Check for Killua
    print("\n--- Checking '奇犽/奇牙' ---")
    c.execute("SELECT id, content, detailed_analysis FROM reviews WHERE content LIKE '%奇犽%' OR content LIKE '%奇牙%' LIMIT 3")
    rows = c.fetchall()
    for r in rows:
        print(f"Content: {r['content'][:30]}...")
        print(f"Analysis: {r['detailed_analysis']}")

    conn.close()

if __name__ == "__main__":
    inspect_db()
