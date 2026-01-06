
# Utilities for crawlers
import datetime
import re
import hashlib
from core.db import save_review

def parse_date(text):
    # 1. Try standard dates YYYY-MM-DD
    match = re.search(r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})', text)
    if match:
        try:
            dt = datetime.datetime.strptime(match.group(1).replace('/', '-'), '%Y-%m-%d')
            return dt, match.group(1)
        except:
            pass
            
    # 2. Try Relative Dates
    try:
        now = datetime.datetime.now()
        text = text.lower()
        
        num_match = re.search(r'(\d+)', text)
        if not num_match: return None, "Unknown"
        val = int(num_match.group(1))
        
        if 'year' in text or '年' in text:
            dt = now - datetime.timedelta(days=365 * val)
            return dt, dt.strftime('%Y-%m-%d')
        elif 'month' in text or '月' in text:
            dt = now - datetime.timedelta(days=30 * val)
            return dt, dt.strftime('%Y-%m-%d')
        elif 'week' in text or '週' in text or '周' in text:
            dt = now - datetime.timedelta(days=7 * val)
            return dt, dt.strftime('%Y-%m-%d')
        elif 'day' in text or '天' in text or '日' in text:
            dt = now - datetime.timedelta(days=val)
            return dt, dt.strftime('%Y-%m-%d')
        elif 'hour' in text or '时' in text or '時' in text:
             return now, now.strftime('%Y-%m-%d')
    except:
        pass

    return None, "Unknown"

def save_review_helper(game_key, author, content, rating, date_str, source, video_title=None, video_url=None, original_date=None):
    review_id = hashlib.md5(f"{author}{date_str}{content}".encode()).hexdigest()
    
    # Validation: If date_str is not YYYY-MM-DD, try to use current date?
    # User said: "unknown" -> use crawl time (today)
    final_date = date_str
    if not re.match(r'\d{4}-\d{2}-\d{2}', date_str):
        final_date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    save_review({
        'id': review_id,
        'game_id': game_key,
        'author': author,
        'rating': rating,
        'content': content,
        'date': final_date,
        'original_date': original_date if original_date else date_str, 
        'source': source,
        'content_title': video_title, # Map param to new db column key
        'content_url': video_url,     # Map param to new db column key
        'video_title': video_title,   # Keep legacy
        'video_url': video_url        # Keep legacy
    })
