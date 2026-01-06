import time
import hashlib
from playwright.sync_api import sync_playwright
from core.db import save_review, init_db
from config.settings import GAMES
import random

import datetime

def run_crawler(game_key="jump_assemble", months_back=24):
    if game_key not in GAMES:
        print(f"Game {game_key} not found.")
        return
        
    game_config = GAMES[game_key]
    
    # Support list of URLs or single URL
    target_urls = game_config.get('urls', [])
    if 'url' in game_config and not target_urls:
        target_urls = [game_config['url']]
        
    # Calculate cutoff date
    today = datetime.datetime.now()
    cutoff_date = today - datetime.timedelta(days=30 * months_back)
    print(f"Target: {game_config['name']}")
    print(f"Time Range: Last {months_back} months (Since {cutoff_date.strftime('%Y-%m-%d')})")
    print(f"URLs: {target_urls}")
    
    init_db()
    
    total_saved = 0
    
    import re
    def parse_date(text):
        match = re.search(r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})', text)
        if match:
            try:
                dt = datetime.datetime.strptime(match.group(1).replace('/', '-'), '%Y-%m-%d')
                return dt, match.group(1)
            except:
                pass
        return None, "Unknown"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Keep False for debug, usually True for prod
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        for url in target_urls:
            try:
                page = context.new_page()
                print(f"Navigating to {url}...")
                page.goto(url)
                time.sleep(random.uniform(2, 5)) 
                
                # Scroll logic
                reviews_collected_on_page = 0
                no_change_count = 0
                
                # Scroll until we hit dates older than cutoff
                reached_cutoff = False
                
                while not reached_cutoff:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(random.uniform(2, 4)) 
                    
                    review_elements = page.locator(".review-item__content").all()
                    current_count = len(review_elements)
                    print(f"  Found {current_count} reviews on page...")
                    
                    if current_count > 0:
                        # Check last few elements for date
                        last_few = review_elements[-5:] 
                        for el in last_few:
                            dt, _ = parse_date(el.inner_text())
                            if dt and dt < cutoff_date:
                                print(f"  Reached old data ({dt.strftime('%Y-%m-%d')}), stopping scroll.")
                                reached_cutoff = True
                                break
                    
                    if current_count == reviews_collected_on_page:
                        no_change_count += 1
                        if no_change_count > 5: # Give it more tries
                            print("  No more content loading.")
                            break
                    else:
                        no_change_count = 0
                        
                    reviews_collected_on_page = current_count
                
                print(f"  Parsing reviews from {url}...")
                review_elements = page.locator(".review-item__content").all()
                
                for el in review_elements:
                    try:
                        author_el = el.locator(".user-name__text").first
                        if not author_el.count(): continue
                        author = author_el.inner_text().strip()
                        
                        content_el = el.locator("a[href*='/review/']").first
                        content = content_el.inner_text().strip() if content_el.count() else el.inner_text().strip()
                        
                        dt_obj, date_str = parse_date(el.inner_text())
                        
                        if dt_obj and dt_obj < cutoff_date:
                            continue # Skip old reviews
                            
                        # Rating
                        stars_container = el.locator(".tap-stars").first
                        rating = stars_container.locator("svg").count() if stars_container.count() else (0 if "期待" in el.inner_text() else -1)
                        
                        # ID Generation helper (inline if missing import)
                        def generate_id(a, d, c):
                            return hashlib.md5(f"{a}{d}{c}".encode()).hexdigest()

                        # Save
                        review_id = generate_id(author, date_str, content)
                        review_data = {
                            'id': review_id,
                            'game_id': game_key,
                            'author': author,
                            'rating': rating,
                            'content': content,
                            'date': date_str
                        }
                        save_review(review_data)
                        total_saved += 1
                    except Exception as e:
                        print(f"Error parsing item: {e}")
                        pass
                
                page.close()
                
            except Exception as e:
                print(f"Error processing URL {url}: {e}")

        print(f"Total saved {total_saved} reviews for {game_config['name']}.")
        browser.close()

        print(f"Total saved {total_saved} reviews for {game_config['name']}.")
        browser.close()

if __name__ == "__main__":
    run_crawler(100)
