import time
import random
import datetime
import json
import os
from core.crawlers.base import parse_date, save_review_helper

BACKUP_FILE = "data/backups/qooapp_backup.jsonl"

def scrape_qooapp(page, url, cutoff_date, game_key):
    source = "qoo" # Standardizing to 'qoo'
    
    # Ensure backup dir
    os.makedirs("data/backups", exist_ok=True)
    
    page.goto(url)
    time.sleep(3)
    
    # 1. Check for "View more reviews" button (Only if not already on comment list)
    if "app-comment" not in url:
        try:
            view_more = page.locator(".game-review__content__more").first
            if view_more.is_visible():
                print(f"  [{source}] Clicking 'View more reviews'...")
                view_more.click()
                page.wait_for_load_state("networkidle")
                time.sleep(3)
        except Exception as e:
            print(f"  [{source}] 'View more' button not found or error. Scraping current page.")
    else:
        print(f"  [{source}] Direct comment list URL detected.")

    # 2. Infinite scroll
    reviews_collected_on_page = 0
    no_change_count = 0
    reached_cutoff = False
    
    while not reached_cutoff:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(2, 4))
        
        current_reviews = page.locator(".comment").all()
        current_count = len(current_reviews)
        
        if current_count > 0:
            last_few = current_reviews[-5:]
            for el in last_few:
                try:
                     time_el = el.locator(".time").first
                     if time_el.count() > 0:
                         date_text = time_el.inner_text().strip()
                         dt_val, _ = parse_date(date_text)
                         if dt_val and dt_val < cutoff_date:
                             reached_cutoff = True
                             print(f"  Reached old data ({date_text}), stopping scroll.")
                             break
                except:
                    pass
        
        if reached_cutoff: break

        if current_count == reviews_collected_on_page:
            no_change_count += 1
            if no_change_count > 5: 
                print(f"  [{source}] No new reviews, stopping.")
                break
        else:
            no_change_count = 0
            # print(f"  [{source}] Looping... found {current_count} reviews.")
            
        reviews_collected_on_page = current_count
        
    # 3. Parse and Save
    reviews = page.locator(".comment").all()
    print(f"  [{source}] Parsing {len(reviews)} items...")
    
    count_saved = 0
    with open(BACKUP_FILE, "a", encoding="utf-8") as f_backup:
        for rev in reviews:
            try:
                author_el = rev.locator(".username").first
                if not author_el.count(): continue
                author = author_el.inner_text().strip()
                
                content_el = rev.locator(".comment-content-box").first
                content = content_el.inner_text().strip() if content_el.count() else ""
                
                rating = 0
                if rev.locator(".score").count() > 0:
                    try:
                        r_text = rev.locator(".score").first.inner_text().strip()
                        rating = float(r_text)
                    except: pass
                
                date_text = "Unknown"
                if rev.locator(".time").count() > 0:
                    date_text = rev.locator(".time").first.inner_text().strip()
                
                dt_obj, date_str = parse_date(date_text)
                if dt_obj and dt_obj < cutoff_date: 
                    continue
                
                # Backup Record
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
                
                save_review_helper(game_key, author, content, rating, date_str, source, original_date=date_text)
                count_saved += 1
            except Exception as e:
                 pass
    print(f"  [{source}] Done. Saved {count_saved} reviews to DB and {BACKUP_FILE}.")
