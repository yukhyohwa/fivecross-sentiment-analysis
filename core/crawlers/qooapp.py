import time
import random
import datetime
from core.crawlers.base import parse_date, save_review_helper

def scrape_qooapp(page, url, cutoff_date, game_key):
    source = "qoo" # Standardizing to 'qoo'
    
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
                         if len(date_text) >= 10:
                             dt_str = date_text[:10]
                             dt = datetime.datetime.strptime(dt_str, '%Y-%m-%d')
                             if dt < cutoff_date:
                                 reached_cutoff = True
                                 print(f"  Reached old data ({dt_str}), stopping scroll.")
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
            print(f"  [{source}] Looping... found {current_count} reviews.")
            
        reviews_collected_on_page = current_count
        
    # 3. Parse
    reviews = page.locator(".comment").all()
    print(f"  [{source}] Parsing {len(reviews)} items...")
    
    for rev in reviews:
        try:
            author = rev.locator(".username").first.inner_text().strip()
            content = rev.locator(".comment-content-box").first.inner_text().strip()
            
            rating = 0
            if rev.locator(".score").count() > 0:
                try:
                    r_text = rev.locator(".score").first.inner_text().strip()
                    rating = float(r_text)
                except: pass
            
            date_str = "Unknown"
            if rev.locator(".time").count() > 0:
                date_str = rev.locator(".time").first.inner_text().strip()
            
            try:
                if len(date_str) >= 10:
                    dt = datetime.datetime.strptime(date_str[:10], '%Y-%m-%d')
                    if dt < cutoff_date: continue
            except: pass
            
            save_review_helper(game_key, author, content, rating, date_str, source, original_date=date_str)
        except Exception as e:
             pass
