import sqlite3
import os
import datetime
import pandas as pd
from pytrends.request import TrendReq
import time

# Use a separate database for market trends
# Correctly point to project root data/ (3 levels up from core/crawlers/..)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_NAME = os.path.join(BASE_DIR, 'data', 'market_trends.db')


def init_trends_db():
    os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS google_trends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT,
            region TEXT,
            date TEXT,
            interest_score INTEGER,
            updated_at TEXT,
            UNIQUE(keyword, region, date)
        )
    ''')
    conn.commit()
    conn.close()

def fetch_google_trends(keywords, regions=['TW', 'HK', 'MY', 'VN']):
    """
    regions: TW (Taiwan), HK (Hong Kong), MY (Malaysia), VN (Vietnam)
    """
    pytrends = TrendReq(hl='zh-TW', tz=360)
    
    for kw in keywords:
        for region in regions:
            print(f"  [google_trends] Fetching for '{kw}' in {region}...")
            try:
                # build_payload for last 3 months to see recent impact
                pytrends.build_payload([kw], cat=0, timeframe='today 3-m', geo=region, gprop='')
                df = pytrends.interest_over_time()
                
                if not df.empty:
                    # Remove 'isPartial' column if it exists
                    if 'isPartial' in df.columns:
                        df = df.drop(columns=['isPartial'])
                    
                    conn = sqlite3.connect(DB_NAME)
                    c = conn.cursor()
                    
                    for date, row in df.iterrows():
                        score = int(row[kw])
                        date_str = date.strftime('%Y-%m-%d')
                        
                        c.execute('''
                            INSERT OR REPLACE INTO google_trends (keyword, region, date, interest_score, updated_at)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (kw, region, date_str, score, datetime.datetime.now().isoformat()))
                    
                    conn.commit()
                    conn.close()
                    print(f"  [google_trends] ✅ Saved {len(df)} days of data for {region}.")
                else:
                    print(f"  [google_trends] ⚠️ No data found for {region}.")
                
                # Sleep to avoid rate limiting
                time.sleep(2)
            except Exception as e:
                print(f"  [google_trends] ❌ Error for {region}: {e}")
                time.sleep(5)

if __name__ == "__main__":
    init_trends_db()
    
    # Regional targeting: 
    # TW/HK use Traditional Chinese
    # BR/US/TH/JP use English "Jump: Assemble" as requested
    configs = [
        {"kw": ["漫畫群星：大集結"], "regions": ["TW", "HK"]},
        {"kw": ["Jump: Assemble"], "regions": ["BR", "US", "TH", "JP"]}
    ]
    
    for config in configs:
        fetch_google_trends(config["kw"], regions=config["regions"])


