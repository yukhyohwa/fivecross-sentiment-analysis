from playwright.sync_api import Page, Locator
import datetime
import time
import random
import json
import os
import re
from .base import save_review_helper, parse_date
from config.settings import DISCORD_USER, DISCORD_PASS

# Unified Backup naming
BACKUP_FILE = "data/backups/discord_backup.jsonl"

def login_discord(page: Page):
    if not DISCORD_USER or not DISCORD_PASS:
        print("  [discord] No credentials found in .env. Waiting for manual login...")
        return

    try:
        print(f"  [discord] Attempting auto-login for {DISCORD_USER}...")
        page.wait_for_selector("input[name='email']", timeout=15000)
        page.fill("input[name='email']", DISCORD_USER)
        page.fill("input[name='password']", DISCORD_PASS)
        page.click("button[type='submit']")
        print("  [discord] Login credentials submitted.")
    except Exception as e:
        print(f"  [discord] Auto-login info: {e}")

def scrape_messages_in_container(container: Locator, game_key, guild_id, channel_id, cutoff_date, f_backup, source, url, topic_title="Unknown"):
    """Helper to scrape messages inside a specific container (e.g., Region 3 sidebar)"""
    count_saved = 0
    try:
        # Wait for messages to load in the container
        container.locator("[class*='messageListItem'], [role='article']").first.wait_for(timeout=10000)
    except:
        return 0

    # Scroll within the thread to load all replies if it's a long thread
    for _ in range(3): 
        container.evaluate("e => e.scrollTop += 5000")
        time.sleep(1.5)

    # After scrolling, collect all messages
    messages = container.locator("[class*='messageListItem'], [role='article']").all()
    seen_msg_ids = set() 
    
    for msg in messages:
        try:
            # Content
            content_el = msg.locator("[id^='message-content-'], [class*='messageContent']")
            if not content_el.count(): continue
            raw_content = content_el.first.inner_text().strip()
            if not raw_content: continue
            
            # Message ID for deduplication
            msg_id = ""
            try:
                msg_id = msg.get_attribute("id") or raw_content[:50]
            except: pass
            
            if msg_id in seen_msg_ids: continue
            seen_msg_ids.add(msg_id)

            # Author
            author_el = msg.locator("[class*='username'], [class*='author']")
            author = author_el.first.inner_text().strip() if author_el.count() else "Anonymous"
            
            # Date
            date_el = msg.locator("time")
            if date_el.count():
                date_text = date_el.first.get_attribute("datetime") or date_el.first.inner_text().strip()
            else:
                date_text = "Unknown"

            dt_obj, date_str = parse_date(date_text)
            
            # FORCE SAVE: If parsing fails, use today's date
            if not dt_obj or date_str == "Unknown":
                date_str = datetime.datetime.now().strftime('%Y-%m-%d')
            
            # Skip only if we have a valid date and it's too old
            is_deep_crawl = (datetime.datetime.now() - cutoff_date).days > 365
            if dt_obj and dt_obj < cutoff_date and not is_deep_crawl:
                continue
            
            record = {
                "game_key": game_key,
                "guild_id": guild_id,
                "channel_id": channel_id,
                "topic_title": topic_title,
                "author": author,
                "content": raw_content,
                "raw_date": date_text,
                "parsed_date": date_str,
                "source": source,
                "url": url,
                "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            f_backup.write(json.dumps(record, ensure_ascii=False) + "\n")
            f_backup.flush()
            
            save_review_helper(
                game_key=game_key, author=author, content=raw_content, rating=0,
                date_str=date_str, source=source, content_title=f"Discord [{topic_title}]", 
                content_url=url, original_date=date_text
            )
            count_saved += 1
        except Exception:
            pass
    return count_saved

def scrape_discord(page: Page, url: str, cutoff_date: datetime.datetime, game_key: str):
    source = "discord"
    os.makedirs("data/backups", exist_ok=True)
    
    match = re.search(r'channels/(\d+)/(\d+)', url)
    guild_id = match.group(1) if match else "unknown"
    channel_id = match.group(2) if match else "unknown"
    
    print(f"  [discord] 🎯 Target: Game Suggestions (ID: {channel_id})")
    
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(10)
        
        # --- EARLY CONTENT DETECTION ---
        # Look for ANY h3 that might be a post title
        h3_count = page.locator("h3").count()
        if h3_count > 0:
            print(f"  [discord] 🚀 Found {h3_count} headings. Assuming content is visible.")
        else:
            # --- LOGIN / STATE DETECTION ---
            if page.locator("input[name='email']").is_visible():
                print("  [discord] 🚩 Login screen detected. Attempting auto-login...")
                login_discord(page)
                try:
                    page.wait_for_selector("[role='main'], [role='navigation']", timeout=60000)
                except: pass
            else:
                print("  [discord] ✅ Already in Discord or login not visible.")

            # --- REGION 1: Sidebar Skip ---
            if f"/{channel_id}" not in page.url:
                print("  [discord] 🔍 Navigating sidebar to '遊戲建議'...")
                try:
                    page.get_by_text("遊戲建議", exact=False).first.click(force=True)
                    time.sleep(5)
                except: pass

        # --- REGION 2: Forum List (Broad Search) ---
        print("  [discord] Loading forum posts (Region 2)...")
        
        seen_posts = set()
        total_saved = 0
        
        with open(BACKUP_FILE, "a", encoding="utf-8") as f_backup:
            max_scrolls = 25
            consecutive_no_new = 0
            
            for s in range(max_scrolls):
                # BROAD SEARCH: Find all H3 headings.
                h3_locators = page.locator("h3").all()
                new_found_this_scroll = 0
                
                print(f"  [discord]   (Scroll {s+1}) Detected {len(h3_locators)} potential titles.")
                
                for title_loc in h3_locators:
                    try:
                        title = title_loc.inner_text().strip()
                        if not title or len(title) < 2 or title in seen_posts: continue
                        if title in ["Official", "Chat", "Forum", "Rules", "Information"]: continue
                        
                        seen_posts.add(title)
                        new_found_this_scroll += 1
                        print(f"  [discord]      👉 [{len(seen_posts)}] Post: {title}")
                        
                        # Click the title or its adjacent clickable parent
                        title_loc.scroll_into_view_if_needed()
                        title_loc.click(force=True)
                        time.sleep(4)
                        
                        # --- REGION 3: Thread Container ---
                        # In Discord Forum, the thread is typically a complementary container or the last chatContent
                        containers = page.locator("[class*='chatContent'], [role='complementary'], [class*='threadSidebar']").all()
                        thread_target = containers[-1] if containers else None
                        
                        if thread_target and thread_target.is_visible():
                            saved = scrape_messages_in_container(thread_target, game_key, guild_id, channel_id, cutoff_date, f_backup, source, url, topic_title=title)
                            total_saved += saved
                            if saved > 0:
                                print(f"  [discord]         ✅ Scraped {saved} messages.")
                        
                        # Close Region 3
                        page.keyboard.press("Escape")
                        time.sleep(1.5)

                    except Exception:
                        pass
                
                if new_found_this_scroll == 0:
                    consecutive_no_new += 1
                else:
                    consecutive_no_new = 0
                    
                if consecutive_no_new >= 4:
                    print("  [discord] No new posts found for 4 scrolls. Ending.")
                    break
                
                # Scroll the whole page down
                page.mouse.wheel(0, 3000)
                time.sleep(3)

        print(f"  [discord] Finished. Total saved: {total_saved}")

    except Exception as e:
        print(f"  [discord] Error during crawl: {e}")
