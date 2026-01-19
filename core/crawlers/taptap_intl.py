import time
import random
import json
import os
from core.crawlers.base import parse_date, save_review_helper


BACKUP_FILE = "data/taptap_intl_backup.jsonl"

def scrape_taptap_intl(page, url, cutoff_date, game_key):
    source = "taptap_intl"
    
    # Ensure backup dir
    os.makedirs("data", exist_ok=True)
    
    page.goto(url)
    time.sleep(random.uniform(2, 5))
    
    reviews_collected_on_page = 0
    no_change_count = 0
    reached_cutoff = False
    
    # Global/International Selectors
    container_sel = ".post-card"
    
    print(f"[{source}] Scrolling to reach cutoff date: {cutoff_date.strftime('%Y-%m-%d')}...")

    
    while not reached_cutoff:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(2, 4))
        
        review_elements = page.locator(container_sel).all()
        current_count = len(review_elements)
        print(f"[{source}] Found {current_count} reviews scrolling...")
        
        # Check the last items to see if we reached the cutoff date
        if current_count > 0:
            last_elements = review_elements[-5:]
            for el in last_elements:
                time_el = el.locator(".tap-time").first
                date_text = ""
                if time_el.count():
                    date_text = time_el.inner_text().strip()
                else:
                    head_el = el.locator(".post-card__head-text").first
                    if head_el.count():
                        date_text = head_el.inner_text().strip()
                
                dt, _ = parse_date(date_text)
                if dt and dt < cutoff_date:
                    print(f"[{source}] Reached cutoff date ({dt.strftime('%Y-%m-%d')}). Stopping scroll.")
                    reached_cutoff = True
                    break
        
        if current_count == reviews_collected_on_page:
            no_change_count += 1
            if no_change_count > 10: # More patient for full crawl
                print(f"[{source}] No more reviews loading (stuck).")
                break
        else:
            no_change_count = 0
            reviews_collected_on_page = current_count
    
    print(f"[{source}] Starting to parse and save reviews...")
    review_elements = page.locator(container_sel).all()
    
    count_saved = 0
    # Open backup file in append mode to avoid losing previous data
    with open(BACKUP_FILE, "a", encoding="utf-8") as f_backup:
        for el in review_elements:
            try:
                # Nickname
                author_el = el.locator(".post-card__head-text span:first-child").first
                if not author_el.count(): continue
                author = author_el.inner_text().strip()
                
                # Content
                content_el = el.locator(".post-card__summary").first
                content = content_el.inner_text().strip() if content_el.count() else ""
                
                # Date logic
                date_text = ""
                time_el = el.locator(".tap-time").first
                if time_el.count():
                    date_text = time_el.inner_text().strip()
                else:
                    head_el = el.locator(".post-card__head-text").first
                    if head_el.count():
                        date_text = head_el.inner_text().strip()
                
                dt_obj, date_str = parse_date(date_text)
                
                # Cutoff check during parsing too
                if dt_obj and dt_obj < cutoff_date:
                    continue
                
                # Rating
                rating = 0
                rating_el = el.locator(".rating-star").first
                if rating_el.count():
                     rating = rating_el.locator(".rating-star__item--active").count()
                
                # 1. Save to Local Backup (JSONL)
                record = {
                    "game_key": game_key,
                    "author": author,
                    "content": content,
                    "rating": rating,
                    "raw_date": date_text,
                    "parsed_date": date_str,
                    "source": source,
                    "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                f_backup.write(json.dumps(record, ensure_ascii=False) + "\n")
                
                # 2. Save to Database
                save_review_helper(game_key, author, content, rating, date_str, source, original_date=date_text)
                
                count_saved += 1
            except Exception as e:
                # print(f"      [Error] {e}")
                pass
                
    print(f"[{source}] Crawl finished. Saved {count_saved} reviews to DB and {BACKUP_FILE}.")
