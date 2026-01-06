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
    game_config = GAMES[game_key]
    
    # Support list of URLs or single URL
    target_urls = game_config.get('urls', [])
    if 'url' in game_config and not target_urls:
        target_urls = [game_config['url']]
        
    print(f"Target: {game_config['name']} (Count: {max_reviews})")
    print(f"URLs: {target_urls}")
    
    init_db()
    
    total_saved = 0
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        for url in target_urls:
            if total_saved >= max_reviews: break
            
            try:
                page = context.new_page()
                print(f"Navigating to {url}...")
                page.goto(url)
                time.sleep(random.uniform(2, 5)) 
                
                # Scroll logic
                reviews_collected_on_page = 0
                no_change_count = 0
                
                # Calculate how many more we need
                remaining = max_reviews - total_saved
                
                # We don't know exactly how many items correspond to scroll height, so we just heuristic scroll
                # But we can check element count
                while True:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(random.uniform(2, 4)) 
                    
                    review_elements = page.locator(".review-item__content").all()
                    current_count = len(review_elements)
                    print(f"  Found {current_count} reviews on page...")
                    
                    if current_count >= remaining:
                         break # Enough loaded
                    
                    if current_count == reviews_collected_on_page:
                        no_change_count += 1
                        if no_change_count > 3: break
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
                        
                        # Rating
                        stars_container = el.locator(".tap-stars").first
                        rating = stars_container.locator("svg").count() if stars_container.count() else (0 if "期待" in el.inner_text() else -1)

                        # Date
                        date_str = "Unknown"
                        import re
                        date_match = re.search(r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})', el.inner_text())
                        if date_match: date_str = date_match.group(1)
                        
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
                        if total_saved >= max_reviews: break
                    except Exception as e:
                        print(f"Error parsing item: {e}")
                        pass
                
                page.close()
                
            except Exception as e:
                print(f"Error processing URL {url}: {e}")

        print(f"Total saved {total_saved} reviews for {game_config['name']}.")
        browser.close()

if __name__ == "__main__":
    run_crawler(100)
