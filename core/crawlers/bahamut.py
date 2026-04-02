from playwright.sync_api import Page
import datetime
import time
import random
import json
import os
from .base import save_review_helper, parse_date
from config.settings import BAHAMUT_USER, BAHAMUT_PASS

# Unified Backup naming
BACKUP_FILE = "data/backups/bahamut_backup.jsonl"

def login_bahamut(page: Page):
    print("  [bahamut] Checking login status...")
    try:
        # First, try to visit a page that shows login status
        page.goto("https://www.gamer.com.tw/")
        time.sleep(2)
        
        # Stricter detection: 
        # If we see "登入" (Login button), we are definitely NOT logged in.
        # If we see "登出" (Logout link) or a specific member name, we ARE logged in.
        is_guest = page.get_by_role("link", name="登入", exact=False).count() > 0
        is_logged_in = page.locator("a[href*='logout.php']").count() > 0 or page.locator(".topbar-member-name").count() > 0
        
        if is_logged_in and not is_guest:
            print("  [bahamut] Already logged in via session.")
            return

        print("  [bahamut] Not logged in. Navigating to Login Page...")
        page.goto("https://user.gamer.com.tw/login.php")
        
        # If redirected away from login.php, we might be logged in
        if "login.php" not in page.url:
            print("  [bahamut] Redirected from login, session might be active.")
            return

        # --- AUTO-FILL ATTEMPT ---
        try:
            if BAHAMUT_USER and BAHAMUT_PASS and BAHAMUT_USER != "guest":
                print(f"  [bahamut] Attempting to auto-fill credentials for {BAHAMUT_USER}...")
                page.fill("input[name='userid']", BAHAMUT_USER, timeout=5000)
                page.fill("input[name='password']", BAHAMUT_PASS, timeout=5000)
                
                # Wait a bit then click login button
                time.sleep(1)
                print("  [bahamut] Clicking Login button...")
                page.click("a#btn-login") 
                
                # Note: If a Cloudflare challenge pops up after click, the loop below will wait
            else:
                print("  [bahamut] No credentials found in .env, skipping auto-fill.")
        except Exception as e:
             print(f"  [bahamut] Auto-fill/Click failed (might be behind captcha): {e}")

        print("  [bahamut] --- MANUAL LOGIN REQUIRED ---")
        print(f"  [bahamut] 1. Solve Cloudflare Captcha.")
        print(f"  [bahamut] 2. Login with {BAHAMUT_USER} / {'*' * len(BAHAMUT_PASS)}.")
        
        # Wait Loop for Login Success
        max_wait = 300 
        start_time = time.time()
        
        while True:
            if time.time() - start_time > max_wait:
                print("  [bahamut] Login timed out. Proceeding as Guest...")
                break
                
            current_url = page.url
            if "login.php" not in current_url and "google.com" not in current_url:
                print(f"  [bahamut] Detected login success!")
                break
            
            # Pure Manual Login Hint
            try:
                # Inject a visual hint for the user
                page.evaluate(f"""() => {{
                    if (document.getElementById('crawler-hint')) return;
                    const div = document.createElement('div');
                    div.id = 'crawler-hint';
                    div.style.position = 'fixed';
                    div.style.top = '10px';
                    div.style.left = '50%';
                    div.style.transform = 'translateX(-50%)';
                    div.style.backgroundColor = '#ff4757';
                    div.style.color = 'white';
                    div.style.padding = '15px 25px';
                    div.style.borderRadius = '12px';
                    div.style.zIndex = '9999999'; // Higher z-index
                    div.style.boxShadow = '0 10px 30px rgba(0,0,0,0.5)';
                    div.style.fontSize = '18px';
                    div.style.fontWeight = 'bold';
                    div.style.border = '3px solid white';
                    div.style.textAlign = 'center';
                    div.innerHTML = `
                        <div style="margin-bottom:8px; font-size:20px; text-decoration:underline;">⚠️ 爬虫正等待登录 ⚠️</div>
                        <div style="margin:10px 0;">账号: <span style="font-family:monospace; background:#000; padding:2px 8px; border-radius:4px;">{BAHAMUT_USER}</span></div>
                        <div style="margin:10px 0;">密码: <span style="font-family:monospace; background:#000; padding:2px 8px; border-radius:4px;">{BAHAMUT_PASS}</span></div>
                        <hr style="border:0; border-top:1px solid rgba(255,255,255,0.3); margin:10px 0;"/>
                        <div style="font-size:14px; font-weight:normal;">请手动填入上方信息，解决验证码并点击登录。<br/>登录成功后此窗口将消失。</div>
                    `;
                    document.body.appendChild(div);
                }}""")
            except: pass
            time.sleep(2)
    except Exception as e:
        print(f"  [bahamut] Login session error: {e}")

def scrape_bahamut(page: Page, url: str, cutoff_date: datetime.datetime, game_key: str):
    source = "bahamut"
    login_bahamut(page)
    
    # Ensure backup dir
    os.makedirs("data/backups", exist_ok=True)
    
    # 1. Get Thread Links
    threads_to_scrape = []
    try:
        page.goto(url)
        page.wait_for_selector(".b-list__main", timeout=20000)
             
        rows = page.locator(".b-list__row").all()
        for row in rows:
            try:
                title_el = row.locator(".b-list__main__title")
                if not title_el.count(): continue
                title = title_el.inner_text().strip()
                href = title_el.get_attribute("href")
                if href:
                    full_url = f"https://forum.gamer.com.tw/{href}" if not href.startswith("http") else href
                    threads_to_scrape.append({"title": title, "url": full_url})
            except: pass
    except Exception as e:
        print(f"  [bahamut] Error getting list: {e}")
        return

    print(f"  [bahamut] Identified {len(threads_to_scrape)} threads.")

    # 2. Visit Threads
    count_saved = 0
    with open(BACKUP_FILE, "a", encoding="utf-8") as f_backup:
        for i, thread in enumerate(threads_to_scrape):
            t_url = thread['url']
            t_title = thread['title']
            
            print(f"  [bahamut] ({i+1}/{len(threads_to_scrape)}) {t_title[:30]}...")
            time.sleep(random.uniform(2, 4))

            try:
                page.goto(t_url)
                page.wait_for_selector("section.c-section", timeout=10000)
                
                posts = page.locator("section.c-section").all()
                for post_idx, post in enumerate(posts):
                    try:
                        content_el = post.locator(".c-article__content")
                        if not content_el.count(): continue
                        raw_content = content_el.inner_text().strip()
                        if not raw_content: continue
                        
                        author_el = post.locator(".c-user__name")
                        author = author_el.inner_text().strip() if author_el.count() else "Anonymous"

                        content = f"【发帖】 {raw_content}" if post_idx == 0 else f"【跟帖】 {raw_content}"
                        
                        # Date Extraction
                        date_text = "Unknown"
                        if post.locator(".c-post__header a[data-href]").count():
                             date_text = post.locator(".c-post__header a[data-href]").first.inner_text().strip()
                        elif post.locator(".c-post__header").count():
                             header_txt = post.locator(".c-post__header").inner_text()
                             import re
                             match = re.search(r'\d{4}-\d{2}-\d{2}', header_txt)
                             if match: date_text = match.group(0)
                        
                        dt_obj, date_str = parse_date(date_text)
                        if dt_obj and dt_obj < cutoff_date: continue
                        
                        # Local Backup
                        record = {
                            "game_key": game_key,
                            "title": t_title,
                            "author": author,
                            "content": content,
                            "raw_date": date_text,
                            "parsed_date": date_str,
                            "source": source,
                            "url": t_url,
                            "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                        f_backup.write(json.dumps(record, ensure_ascii=False) + "\n")
                        
                        save_review_helper(
                            game_key=game_key, author=author, content=content, rating=0,
                            date_str=date_str, source=source, content_title=t_title, 
                            content_url=t_url, original_date=date_text
                        )
                        count_saved += 1
                    except Exception: pass
            except Exception: pass
    
    print(f"  [{source}] Done. Saved {count_saved} posts to DB and {BACKUP_FILE}.")
