from playwright.sync_api import Page
import datetime
import time
import random
import json
import os
import re
from .base import save_review_helper, parse_date
from config.settings import DISCORD_USER, DISCORD_PASS

# Unified Backup naming
BACKUP_FILE = "data/discord_backup.jsonl"

def login_discord(page: Page):
    if not DISCORD_USER or not DISCORD_PASS:
        print("  [discord] No credentials found in .env. Waiting for manual login...")
        return

    try:
        print(f"  [discord] Attempting auto-login for {DISCORD_USER}...")
        # Fill email and password using stable selectors
        page.wait_for_selector("input[name='email']", timeout=15000)
        page.fill("input[name='email']", DISCORD_USER)
        page.fill("input[name='password']", DISCORD_PASS)
        
        # Click login button
        page.click("button[type='submit']")
        print("  [discord] Login credentials submitted.")
    except Exception as e:
        print(f"  [discord] Auto-login info: {e}")

def scrape_messages_in_current_view(page: Page, game_key, guild_id, channel_id, cutoff_date, f_backup, source, url, topic_title="Unknown"):
    """Helper to scrape messages visible in the current view (chat or open thread)"""
    count_saved = 0
    # Search for messages - Discord uses obfuscated classes, so we use multiple attributes
    try:
        # Reduced timeout for faster checks
        page.wait_for_selector("[class*='messageListItem'], [id^='message-content-'], [role='article']", timeout=10000)
    except:
        return 0
        
    # Use a more generic selector to find message blocks
    messages = page.locator("[class*='messageListItem']").all()
    if not messages:
        messages = page.locator("[role='article']").all()

    # If it's a forum thread, we want the messages
    # print(f"  [discord] Scanned {len(messages)} items in '{topic_title}'")

    for msg in messages:
        try:
            # Content
            content_el = msg.locator("[id^='message-content-'], [class*='messageContent']")
            if not content_el.count(): continue
            raw_content = content_el.first.inner_text().strip()
            if not raw_content: continue
            
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
            
            # ISO parsing
            if not dt_obj and date_text != "Unknown":
                try:
                    iso_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', date_text)
                    if iso_match:
                        dt_obj = datetime.datetime.fromisoformat(iso_match.group(1))
                        date_str = dt_obj.strftime('%Y-%m-%d')
                except: pass

            # Deep crawl logic: keep if days_back is very large
            is_deep_crawl = (datetime.datetime.now() - cutoff_date).days > 365
            
            if not dt_obj:
                if not is_deep_crawl: continue
                date_str = "2024-01-01" # Sentinel
            elif dt_obj < cutoff_date and not is_deep_crawl:
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
            # Save to backup
            f_backup.write(json.dumps(record, ensure_ascii=False) + "\n")
            f_backup.flush()
            
            # Save to DB
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
    """
    Scrapes Discord Forum threads specifically for 'Game Suggestions'.
    """
    source = "discord"
    os.makedirs("data", exist_ok=True)
    
    match = re.search(r'channels/(\d+)/(\d+)', url)
    guild_id = match.group(1) if match else "unknown"
    channel_id = match.group(2) if match else "unknown"
    
    print(f"  [discord] 🎯 目标频道: 游戏建议 (ID: {channel_id})")
    
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # --- LOGIN / STATE DETECTION ---
        print("  [discord] 正在检查登录状态...")
        
        # Wait a bit or check if login form appears (Discord can be slow)
        try:
            page.wait_for_selector("input[name='email']", timeout=10000)
        except:
            pass

        if page.locator("input[name='email']").is_visible():
            login_discord(page)
            print("  [discord] 登录指令已发送，正在进入频道...")
            try:
                # Give it time to transition from login to main content
                page.wait_for_selector("[role='main'], [aria-label*='New Post']", timeout=45000) 
            except:
                pass
            time.sleep(5) # Short buffer for dynamic elements to settle

        # --- FORUM MODE ACTIVATION ---
        print("  [discord] 正在定位论坛贴子列表 (最多等待 30s)...")
        
        main_area = page.locator("[role='main']")
        is_forum = False
        
        # Retry loop for detection (Discord forum is slow to render)
        for attempt in range(6):
            selectors_to_check = [
                "div[class*='mainCard']", 
                "[aria-label*='New Post']", 
                "[aria-label*='新贴子']",
                "[aria-label*='新貼文']", # Traditional Chinese
                "[aria-label*='貼子']",   # Traditional Chinese
                "[aria-label*='帖子']",   
                "[class*='container-'] [class*='card-']",
                "[class*='form-'] [class*='searchInput-']", 
                "[role='list'][aria-label*='贴子']",
                "[role='list'][aria-label*='Post']",
                "[role='list'][aria-label*='貼子']"
            ]
            
            for selector in selectors_to_check:
                if main_area.locator(selector).count() > 0:
                    is_forum = True
                    print(f"  [discord] 成功匹配到论坛元素: {selector}")
                    break
            
            if is_forum or "threads" in page.url:
                is_forum = True
                break
                
            print(f"  [discord] 暂未发现论坛特征，等待中... ({attempt+1}/6)")
            time.sleep(5)
        
        # Final desperate check: if we see message-like items but no forum cards, it might be a normal channel
        # But for 'Game Suggestions' it SHOULD be a forum.
        
        total_saved = 0
        with open(BACKUP_FILE, "a", encoding="utf-8") as f_backup:
            if is_forum:
                print("  [discord] 确认进入论坛视图，正在加载贴子列表...")
                # Ensure we have cards before scrolling
                try:
                    main_area.locator("div[class*='mainCard'], [class*='card-']").first.wait_for(timeout=15000)
                except: pass

                # Scroll to load history
                for _ in range(10):
                    page.mouse.wheel(0, 5000)
                    time.sleep(2)
                
                # Check for cards again using multiple possible classes
                post_cards = main_area.locator('div[class*="mainCard"], [class*="card-"]').all()
                if not post_cards:
                    print("  [discord] ❌ 未找到任何建议贴子（可能是权限不足或页面未加载）。")
                    return

                print(f"  [discord] 找到 {len(post_cards)} 个建议贴。")
                
                for i in range(len(post_cards)):
                    if i >= 150: break # Safety limit
                    try:
                        # Re-locate cards as DOM might update
                        current_cards = main_area.locator('div[class*="mainCard"]').all()
                        if i >= len(current_cards): break
                        card = current_cards[i]
                        
                        # Get Title
                        title_el = card.locator("h3").first
                        title = title_el.inner_text().strip() if title_el.count() else f"贴子 {i}"
                        
                        # Safety: Skip categories/system channels
                        if title in ["官方消息", "聊天空間", "建議空間", "組隊空間", "General", "Lobby"]:
                            continue

                        print(f"  [discord] ({i+1}/{len(current_cards)}) 正在进入原贴: {title}")
                        
                        # Click into thread
                        card.scroll_into_view_if_needed()
                        card.click(force=True)
                        time.sleep(5) # Wait for thread content
                        
                        # Scrape Messages
                        saved = scrape_messages_in_current_view(page, game_key, guild_id, channel_id, cutoff_date, f_backup, source, url, topic_title=title)
                        if saved > 0:
                            print(f"  [discord]     ✅ 已抓取 {saved} 条回复。")
                        total_saved += saved
                        
                        # Close Thread to return to list
                        page.keyboard.press("Escape")
                        time.sleep(1.5)
                        close_btn = page.locator("[aria-label='Close'], [aria-label='关闭']").first
                        if close_btn.is_visible():
                            close_btn.click()
                            time.sleep(1)
                            
                    except Exception:
                        pass
            else:
                print("  [discord] ❌ 错误：当前地址不是有效的论坛频道。Discord 爬虫仅支持‘游戏建议’类的论坛视图。")
                return
                    
        print(f"  [discord] 完成。共计保存 {total_saved} 条‘游戏建议’相关数据。")

    except Exception as e:
        print(f"  [discord] 抓取过程出错: {e}")
