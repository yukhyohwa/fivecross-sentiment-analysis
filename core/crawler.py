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
                
                # Identify Source
                source = "taptap_android"
                if "taptap" in url:
                    if "os=ios" in url: source = "taptap_ios"
                    elif "taptap.io" in url: source = "taptap_global"
                    scrape_taptap(page, url, source, cutoff_date, game_key)
                elif "youtube" in url:
                    source = "youtube"
                    scrape_youtube(page, url, source, cutoff_date, game_key)
                elif "qoo-app" in url:
                    source = "qooapp"
                    scrape_qooapp(page, url, source, cutoff_date, game_key)
                else:
                    print(f"Unknown source for URL: {url}")
                
                page.close()
                
            except Exception as e:
                print(f"Error processing URL {url}: {e}")

        browser.close()

def scrape_taptap(page, url, source, cutoff_date, game_key):
    page.goto(url)
    time.sleep(random.uniform(2, 5))
    
    # Scroll logic
    reviews_collected_on_page = 0
    no_change_count = 0
    reached_cutoff = False
    
    while not reached_cutoff:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(2, 4))
        
        review_elements = page.locator(".review-item__content").all()
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
    review_elements = page.locator(".review-item__content").all()
    
    for el in review_elements:
        try:
            author_el = el.locator(".user-name__text").first
            if not author_el.count(): continue
            author = author_el.inner_text().strip()
            
            content_el = el.locator("a[href*='/review/']").first
            content = content_el.inner_text().strip() if content_el.count() else el.inner_text().strip()
            
            dt_obj, date_str = parse_date(el.inner_text())
            if dt_obj and dt_obj < cutoff_date: continue
            
            stars_container = el.locator(".tap-stars").first
            rating = stars_container.locator("svg").count() if stars_container.count() else -1
            
            save_review_helper(game_key, author, content, rating, date_str, source)
        except Exception as e:
            pass

def scrape_youtube(page, url, source, cutoff_date, game_key):
    # Go to Videos tab
    if "/@" in url and "/videos" not in url:
        url = url.rstrip('/') + "/videos"
    page.goto(url)
    time.sleep(3)
    
    # Pick first 3 videos
    videos = page.locator("ytd-rich-grid-media a#video-title-link").all()[:3]
    video_urls = [v.get_attribute("href") for v in videos]
    
    for v_url in video_urls:
        if not v_url: continue
        full_url = "https://www.youtube.com" + v_url
        print(f"  Scraping video: {full_url}")
        
        p_vid = page.context.new_page()
        p_vid.goto(full_url)
        time.sleep(5)
        
        # Scroll to comments
        p_vid.evaluate("window.scrollTo(0, 600)")
        time.sleep(2)
        
        # Expand comments
        for _ in range(5):
             p_vid.evaluate("window.scrollTo(0, document.body.scrollHeight)")
             time.sleep(2)
             
        comments = p_vid.locator("ytd-comment-thread-renderer").all()
        print(f"  Found {len(comments)} comments.")
        
        for comm in comments:
            try:
                author = comm.locator("#author-text span").first.inner_text().strip()
                content = comm.locator("#content-text").first.inner_text().strip()
                time_text = comm.locator("#published-time-text a").first.inner_text().strip()
                
                # Approximate date from "2 months ago", etc.
                # Simplifying: just save it directly for now, parser optimization needed later
                date_str = time_text
                
                # Only save if content is valid
                if content:
                    save_review_helper(game_key, author, content, 0, date_str, source)
            except:
                pass
        p_vid.close()

def scrape_qooapp(page, url, source, cutoff_date, game_key):
    # QooApp structure is different. Usually review-card
    # m-apps url provided: https://m-apps.qoo-app.com/en-US/app/31187
    # Usually need to go to /comments or click tab
    page.goto(url)
    time.sleep(3)
    
    # Try to find "Reviews" tab or section
    # On mobile view, might just be list.
    # qoo-app selector guess: .comment-card
    
    # Scroll a bit
    for _ in range(5):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        
    reviews = page.locator(".comment-card, .review-card").all()
    # Fallback to generic article search if specific class unknown
    if not reviews:
        reviews = page.locator("article").all()
        
    print(f"  [{source}] Found {len(reviews)} potential items...")
    
    for rev in reviews:
        try:
            author = rev.locator(".name, .user-name").first.inner_text().strip()
            content = rev.locator(".content, .review-body").first.inner_text().strip()
            
            # Rating
            rating = 0 # Default
            
            save_review_helper(game_key, author, content, rating, "Unknown", source)
        except:
             pass

def save_review_helper(game_key, author, content, rating, date_str, source):
    review_id = hashlib.md5(f"{author}{date_str}{content}".encode()).hexdigest()
    save_review({
        'id': review_id,
        'game_id': game_key,
        'author': author,
        'rating': rating,
        'content': content,
        'date': date_str,
        'source': source
    })
    
def parse_date(text):
    import re
    match = re.search(r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})', text)
    if match:
        try:
            dt = datetime.datetime.strptime(match.group(1).replace('/', '-'), '%Y-%m-%d')
            return dt, match.group(1)
        except:
            pass
    return None, "Unknown"

if __name__ == "__main__":
    run_crawler(100)
