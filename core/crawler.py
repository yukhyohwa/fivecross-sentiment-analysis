import time
import os
from playwright.sync_api import sync_playwright
from core.db import init_db
from config.settings import GAMES
import datetime

# Import crawler modules
from core.crawlers import scrape_taptap_cn, scrape_taptap_intl, scrape_youtube, scrape_qooapp, scrape_bahamut

def run_crawler(game_key="jump_assemble", days_back=None, source_filter=None):
    if game_key not in GAMES:
        print(f"Game {game_key} not found.")
        return
        
    game_config = GAMES[game_key]
    
    # default from config or 30 days
    if days_back is None:
        days_back = game_config.get('crawl_days', 365) # Default to 1 year if not specified
    
    target_urls = game_config.get('urls', [])
    if 'url' in game_config and not target_urls:
        target_urls = [game_config['url']]
        
    today = datetime.datetime.now()
    cutoff_date = today - datetime.timedelta(days=days_back)
    print(f"Target: {game_config['name']}")
    print(f"Time Range: Last {days_back} days (Since {cutoff_date.strftime('%Y-%m-%d')})")
    
    # Apply Source Filter
    if source_filter:
        # Alias handling for usability
        if source_filter.lower() == "bahamut":
            source_filter = "gamer.com.tw"
        elif source_filter.lower() == "discord":
            source_filter = "discord.com"

            
        print(f"Filter: Only scraping sources containing '{source_filter}'")
        target_urls = [u for u in target_urls if source_filter in u]
        
    if not target_urls:
        print("No URLs to scrape after filtering.")
        return

    print(f"URLs to process: {target_urls}")
    
    init_db()
    
    # Path for session persistence
    session_dir = "data/sessions"
    os.makedirs(session_dir, exist_ok=True)
    state_path = os.path.join(session_dir, "storage_state.json")
    
    with sync_playwright() as p:
        # Launch with flags to reduce bot detection
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled'] 
        )
        
        # Load existing session if available
        context_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {'width': 1280, 'height': 800}
        }
        if os.path.exists(state_path):
            print(f"Loading existing session from {state_path}")
            context_kwargs["storage_state"] = state_path
            
        context = browser.new_context(**context_kwargs)
        
        for url in target_urls:
            try:
                page = context.new_page()
                print(f"Navigating to {url}...")
                
                # Dispatcher Logic
                if "taptap.cn" in url:
                    scrape_taptap_cn(page, url, cutoff_date, game_key)
                elif "taptap.io" in url:
                    scrape_taptap_intl(page, url, cutoff_date, game_key)
                elif "youtube" in url or "youtu.be" in url:
                    scrape_youtube(page, url, cutoff_date, game_key)
                elif "qoo-app" in url:
                    scrape_qooapp(page, url, cutoff_date, game_key)
                elif "forum.gamer.com.tw" in url:
                    scrape_bahamut(page, url, cutoff_date, game_key)
                elif "discord.com" in url:
                    # Redirected to local import logic
                    print(f"  [discord] Redirecting {url} to local TXT import...")
                    from core.utils.discord_helper import import_discord_files
                    import_discord_files(game_id=game_key)
                    # No page navigation needed for discord
                    page.close()
                    continue

                else:
                    print(f"Unknown source for URL: {url}")
                
                page.close()
                
            except Exception as e:
                print(f"Error processing URL {url}: {e}")

        # Save session for next time
        print(f"Saving session to {state_path}...")
        context.storage_state(path=state_path)
        browser.close()

if __name__ == "__main__":
    run_crawler("jump_assemble", days_back=365)
