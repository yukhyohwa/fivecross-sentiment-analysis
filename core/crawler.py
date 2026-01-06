import time
import hashlib
from playwright.sync_api import sync_playwright
from core.db import save_review, init_db
from config.settings import GAMES
import random

def run_crawler(game_key="jump_assemble", max_reviews=100):
    if game_key not in GAMES:
        print(f"Game {game_key} not found.")
        return
        
    game_config = GAMES[game_key]
    url = game_config['url']
    print(f"Target: {game_config['name']} ({url})")
    
    init_db()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print(f"Navigating to {url}...")
        page.goto(url)
        # Random sleep to mimic human
        time.sleep(random.uniform(2, 5)) 
        
        # Scroll logic
        reviews_collected = 0
        no_change_count = 0
        
        while reviews_collected < max_reviews:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            # Slower scrolling
            time.sleep(random.uniform(3, 6)) 
            
            review_elements = page.locator(".review-item__content").all()
            current_count = len(review_elements)
            print(f"Found {current_count} reviews...")
            
            if current_count == reviews_collected:
                no_change_count += 1
                if no_change_count > 3: break
            else:
                no_change_count = 0
                
            reviews_collected = current_count
            if reviews_collected >= max_reviews: break
        
        print("Parsing reviews...")
        review_elements = page.locator(".review-item__content").all()
        
        count = 0
        for el in review_elements:
            try:
                # ... (Parsing logic remains similar)
                author_el = el.locator(".user-name__text").first
                if not author_el.count(): continue
                author = author_el.inner_text().strip()
                
                content_el = el.locator("a[href*='/review/']").first
                content = content_el.inner_text().strip() if content_el.count() else el.inner_text().strip()
                
                # Rating
                stars_container = el.locator(".tap-stars").first
                rating = stars_container.locator("svg").count() if stars_container.count() else (0 if "期待" in el.inner_text() else -1)

                # Date
                date_str = "Unknown"
                import re
                date_match = re.search(r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})', el.inner_text())
                if date_match: date_str = date_match.group(1)
                
                # Save with Game ID
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
                count += 1
                if count >= max_reviews: break
            except Exception as e:
                pass
                
        print(f"Saved {count} reviews for {game_config['name']}.")
        browser.close()

if __name__ == "__main__":
    run_crawler(100)
