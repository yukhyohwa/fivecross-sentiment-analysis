import time
import random
import json
import os
from core.crawlers.base import parse_date, save_review_helper

BACKUP_FILE = "data/taptap_cn_backup.jsonl"

def scrape_taptap_cn(page, url, cutoff_date, game_key):
    # CN Source name
    source = "taptap"
    
    # Ensure backup dir
    os.makedirs("data", exist_ok=True)
    
    page.goto(url)
    time.sleep(random.uniform(2, 5))
    
    reviews_collected_on_page = 0
    no_change_count = 0
    reached_cutoff = False
    
    container_sel = ".review-item__content"
    
    while not reached_cutoff:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(2, 4))
        
        # Check for "Expand hidden reviews" button
        try:
            expand_btn = page.locator("xpath=//button[contains(., '已收起')] | //div[contains(@class, 'switch-btn')]").first
            if expand_btn.count() > 0 and expand_btn.is_visible():
                print(f"  [{source}] Clicking expand button...")
                expand_btn.click()
                time.sleep(2)
        except:
            pass
        
        review_elements = page.locator(container_sel).all()
        current_count = len(review_elements)
        print(f"  [{source}] Found {current_count} reviews...")
        
        if current_count > 0:
            last_few = review_elements[-5:] 
            for el in last_few:
                dt, _ = parse_date(el.inner_text())
                if dt and dt < cutoff_date:
                    print(f"  Reached old data ({dt.strftime('%Y-%m-%d')}), stopping.")
                    reached_cutoff = True
                    break
        
        if current_count == reviews_collected_on_page:
            no_change_count += 1
            if no_change_count > 5: break
        else:
            no_change_count = 0
            reviews_collected_on_page = current_count
    
    print(f"  Parsing {source}...")
    review_elements = page.locator(container_sel).all()
    
    count_saved = 0
    with open(BACKUP_FILE, "a", encoding="utf-8") as f_backup:
        for el in review_elements:
            try:
                author_el = el.locator(".user-name__text").first
                if not author_el.count(): continue
                author = author_el.inner_text().strip()
                
                content_el = el.locator("a[href*='/review/']").first
                content = content_el.inner_text().strip() if content_el.count() else el.inner_text().strip()
                
                raw_text = el.inner_text()
                dt_obj, date_str = parse_date(raw_text)
                if dt_obj and dt_obj < cutoff_date: continue
                
                # Improved Rating Parsing
                rating = -1
                # 1. Check for "Expectation" (non-star rating for pre-registration games)
                expect_el = el.locator(".tap-text").first
                if expect_el.count() and "期待" in expect_el.inner_text():
                    rating = 0 # Map "Expectation" to 0
                else:
                    # 2. Check for actual stars
                    stars_highlight = el.locator(".review-rate__highlight").first
                    if stars_highlight.count():
                        style = stars_highlight.get_attribute("style") or ""
                        # Style looks like "width: 90px;" where each star is 18px
                        if "width" in style:
                            try:
                                width_px = float(style.split(":")[1].replace("px", "").replace(";", "").strip())
                                rating = int(round(width_px / 18.0))
                            except:
                                rating = -1
                
                # Backup Raw
                record = {
                    "game_key": game_key,
                    "author": author,
                    "content": content,
                    "rating": rating,
                    "raw_date": raw_text,
                    "parsed_date": date_str,
                    "source": source,
                    "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                f_backup.write(json.dumps(record, ensure_ascii=False) + "\n")
                
                save_review_helper(game_key, author, content, rating, date_str, source, original_date=raw_text)
                count_saved += 1
            except Exception as e:
                pass
    print(f"  [{source}] Saved {count_saved} reviews to DB and {BACKUP_FILE}")
