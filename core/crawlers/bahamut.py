from playwright.sync_api import Page
import datetime
import time
import random
import json
import os
from .base import save_review_helper, parse_date

# Backup file path
BACKUP_FILE = "data/bahamut_raw_backup.jsonl"

def login_bahamut(page: Page):
    print("  [bahamut] Navigating to Login Page...")
    try:
        # Navigate to login
        page.goto("https://user.gamer.com.tw/login.php")
        
        print("  [bahamut] --- MANUAL LOGIN REQUIRED ---")
        print("  [bahamut] Please interact with the browser window:")
        print("  [bahamut] 1. Solve Cloudflare Captcha.")
        print("  [bahamut] 2. Enter Username/Password (bahauser1y9 / mt1y9999).")
        print("  [bahamut] 3. Solve 2FA/Slider.")
        print("  [bahamut] 4. Wait until you are redirected to the homepage.")
        print("  [bahamut] Script is waiting for URL to change from 'login.php'...")

        # Wait Loop for Login Success
        max_wait = 300 # 5 minutes
        start_time = time.time()
        
        while True:
            if time.time() - start_time > max_wait:
                print("  [bahamut] Login timed out. Proceeding as Guest...")
                break
                
            current_url = page.url
            if "login.php" not in current_url and "google.com" not in current_url:
                print(f"  [bahamut] Detected login success! (URL: {current_url})")
                break
            
            # Helper: If we see the form, try to autofill for convenience, but don't force it
            try:
                if page.locator("input[name='userid']").is_visible() and page.locator("input[name='userid']").input_value() == "":
                    print("  [bahamut] Form detected, trying to autofill helper...")
                    page.fill("input[name='userid']", "bahauser1y9")
                    page.fill("input[name='password']", "mt1y9999")
            except:
                pass
                
            time.sleep(2)
            
    except Exception as e:
        print(f"  [bahamut] Login navigation failed: {e}")

def scrape_bahamut(page: Page, url: str, cutoff_date: datetime.datetime, game_key: str):
    source = "bahamut"
    
    # Perform Manual Login Wait
    login_bahamut(page)
    
    print(f"  [bahamut] Scraping Bahamut Board: {url}")
    
    # Ensure backup dir
    os.makedirs("data", exist_ok=True)
    
    # 1. Get Thread Links
    threads_to_scrape = []
    try:
        page.goto(url)
        # Cloudflare wait again just in case
        try:
             page.wait_for_selector(".b-list__main", timeout=20000)
        except:
             print("  [bahamut] Waiting for list... (Manual CF check)")
             page.wait_for_selector(".b-list__main", timeout=60000)
             
        rows = page.locator(".b-list__row").all()
        print(f"  [bahamut] Found {len(rows)} rows.")
        
        for row in rows:
            try:
                title_el = row.locator(".b-list__main__title")
                if not title_el.count(): continue
                title = title_el.inner_text().strip()
                href = title_el.get_attribute("href")
                if href:
                    if not href.startswith("http"):
                        full_url = f"https://forum.gamer.com.tw/{href}"
                    else:
                        full_url = href
                    threads_to_scrape.append({"title": title, "url": full_url})
            except: pass
    except Exception as e:
        print(f"  [bahamut] Error getting list: {e}")
        return

    print(f"  [bahamut] identified {len(threads_to_scrape)} threads.")

    # 2. Visit Threads
    count_saved = 0
    with open(BACKUP_FILE, "a", encoding="utf-8") as f_backup:
        for i, thread in enumerate(threads_to_scrape):
            t_url = thread['url']
            t_title = thread['title']
            
            delay = random.uniform(3, 6)
            print(f"  [bahamut] ({i+1}/{len(threads_to_scrape)}) {t_title}")
            time.sleep(delay)

            try:
                page.goto(t_url)
                page.wait_for_selector("section.c-section", timeout=10000)
                
                posts = page.locator("section.c-section").all()
                for post_idx, post in enumerate(posts):
                    try:
                        # Content
                        content_el = post.locator(".c-article__content")
                        if not content_el.count(): continue
                        raw_content = content_el.inner_text().strip()
                        if not raw_content: continue
                        
                        # Author
                        author = "Anonymous"
                        author_el = post.locator(".c-user__name")
                        if author_el.count(): author = author_el.inner_text().strip()

                        # Prefix
                        content = f"【发帖】 {raw_content}" if post_idx == 0 else f"【跟帖】 {raw_content}"
                        
                        # Date Extraction
                        # Try multiple selectors for date
                        date_text = "Unknown"
                        # 1. Desktop header link
                        if post.locator(".c-post__header a[data-href]").count():
                             date_text = post.locator(".c-post__header a[data-href]").first.inner_text().strip()
                        # 2. Mobile header text
                        elif post.locator(".c-post__header").count():
                             header_txt = post.locator(".c-post__header").inner_text()
                             # Extract YYYY-MM-DD
                             import re
                             match = re.search(r'\d{4}-\d{2}-\d{2}', header_txt)
                             if match: date_text = match.group(0)
                        
                        # Backup first
                        record = {
                            "game_key": game_key,
                            "title": t_title,
                            "author": author,
                            "content": content,
                            "date": date_text,
                            "url": t_url
                        }
                        f_backup.write(json.dumps(record, ensure_ascii=False) + "\n")
                        
                        # DB Usage
                        dt, date_str = parse_date(date_text)
                        
                        # Fallback date if parse failed
                        if date_str == "Unknown":
                             date_str = datetime.datetime.now().strftime('%Y-%m-%d')

                        save_review_helper(
                            game_key=game_key,
                            author=author,
                            content=content,
                            rating=0,
                            date_str=date_str,
                            source=source,
                            video_title=t_title, 
                            video_url=t_url,
                            original_date=date_text
                        )
                        count_saved += 1
                        
                    except Exception as e:
                        # print(f"Post error: {e}")
                        pass
            except Exception as e:
                print(f"  [bahamut] Thread error: {e}")
    
    print(f"  [bahamut] Done. Saved {count_saved} posts to DB and {BACKUP_FILE}")
