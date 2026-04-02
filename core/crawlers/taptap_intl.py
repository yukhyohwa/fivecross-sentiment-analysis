import time
import random
import json
import os
from core.crawlers.base import parse_date, save_review_helper


BACKUP_FILE = "data/backups/taptap_intl_backup.jsonl"

def scrape_taptap_intl(page, url, cutoff_date, game_key):
    source = "taptap_intl"
    
    # Ensure backup dir
    os.makedirs("data/backups", exist_ok=True)
    
    page.goto(url)
    time.sleep(random.uniform(2, 5))
    
    # --- AUTO-DETECT FORMAT ---
    is_post_detail = "/post/" in url
    if is_post_detail:
        print(f"[{source}] Detected post detail format. Scraping comments...")
        container_sel = ".comment-item"
        author_sel = ".comment-item__user-name"
        content_sel = ".comment-item__content"
        time_sel = ".comment-item__time"
    else:
        print(f"[{source}] Detected review list format.")
        container_sel = ".post-card"
        author_sel = ".post-card__head-text span:first-child"
        content_sel = ".post-card__summary"
        time_sel = ".tap-time"
    
    reviews_collected_on_page = 0
    no_change_count = 0
    reached_cutoff = False
    
    print(f"[{source}] Scrolling to reach cutoff date: {cutoff_date.strftime('%Y-%m-%d')}...")
    
    while not reached_cutoff:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(2, 4))
        
        # Check for "Show more" or similar buttons on posts
        try:
            more_btn = page.locator("button:has-text('Read More'), button:has-text('See More')").first
            if more_btn.count() > 0 and more_btn.is_visible():
                more_btn.click()
                time.sleep(2)
        except: pass
        
        review_elements = page.locator(container_sel).all()
        current_count = len(review_elements)
        print(f"[{source}] Found {current_count} items scrolling...")
        
        # Check the last items to see if we reached the cutoff date
        if current_count > 0:
            last_elements = review_elements[-5:]
            for el in last_elements:
                date_text = ""
                try:
                    t_el = el.locator(time_sel).first
                    if t_el.count():
                        date_text = t_el.inner_text().strip()
                except: pass
                
                if not date_text and not is_post_detail:
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
            if no_change_count > 8: 
                break
        else:
            no_change_count = 0
            reviews_collected_on_page = current_count
    
    print(f"[{source}] Starting to parse and save items...")
    review_elements = page.locator(container_sel).all()
    
    count_saved = 0
    with open(BACKUP_FILE, "a", encoding="utf-8") as f_backup:
        for el in review_elements:
            try:
                # Author
                a_el = el.locator(author_sel).first
                if not a_el.count(): continue
                author = a_el.inner_text().strip()
                
                # Content
                c_el = el.locator(content_sel).first
                content = c_el.inner_text().strip() if c_el.count() else ""
                if not content and is_post_detail: # Try deeper for comment text
                    content = el.locator(".comment-item__text").first.inner_text().strip()

                # Date
                date_text = ""
                t_el = el.locator(time_sel).first
                if t_el.count():
                    date_text = t_el.inner_text().strip()
                
                dt_obj, date_str = parse_date(date_text)
                if dt_obj and dt_obj < cutoff_date:
                    continue
                
                # Rating (Post detail doesn't have stars usually)
                rating = 0
                if not is_post_detail:
                    rating_el = el.locator(".rating-star").first
                    if rating_el.count():
                         rating = rating_el.locator(".rating-star__item--active").count()
                
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
            except Exception: pass
                
    print(f"[{source}] Finished. Saved {count_saved} items to DB.")
