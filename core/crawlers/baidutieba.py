from playwright.sync_api import Page
import datetime
import time
import random
import os
import json
from .base import save_review_helper, parse_date
from config.settings import BAIDU_USER, BAIDU_PASS

# Backup File
BACKUP_FILE = "data/baidutieba_backup.jsonl"

def login_baidutieba(page: Page):
    print("  [baidutieba] Checking login status...")
    try:
        page.goto("https://tieba.baidu.com/index.html")
        time.sleep(2)
        
        # Check if already logged in (look for user menu)
        if page.locator(".u_username_title, .u_username").count() > 0:
            print("  [baidutieba] Already logged in.")
            return

        print("  [baidutieba] Initiating login flow...")
        # Click Top Login Button
        login_btn = page.locator(".u_login a, .u_login, #com_userbar .u_login")
        if login_btn.count() > 0:
            login_btn.first.click()
        
        # Wait for dialog
        # Baidu Login Dialog ID: passport-login-pop-dialog
        try:
            page.wait_for_selector(".tang-pass-pop-login", timeout=5000)
        except:
            print("  [baidutieba] Login dialog not detected automatically.")
            
        print(f"  [baidutieba] Attempting to fill credentials: {BAIDU_USER} / ********")
        
        # Select Username/Password Tab (TANGRAM__PSP_11__footerULoginBtn is common ID for 'Username Login' switch)
        try:
            page.click("#TANGRAM__PSP_11__footerULoginBtn", timeout=2000)
        except: pass
        
        # Fill inputs
        try:
            page.fill("#TANGRAM__PSP_11__userName", BAIDU_USER, timeout=2000)
            page.fill("#TANGRAM__PSP_11__password", BAIDU_PASS, timeout=2000)
            
            # Click Submit
            page.click("#TANGRAM__PSP_11__submit", timeout=2000)
        except:
            print("  [baidutieba] Could not auto-fill. Please fill manually.")

        # Manual Intervention Hint
        try:
            page.evaluate(f"""() => {{
                const div = document.createElement('div');
                div.style.position = 'fixed';
                div.style.top = '10px'; 
                div.style.left = '50%';
                div.style.transform = 'translateX(-50%)';
                div.style.backgroundColor = '#2980b9'; 
                div.style.color = 'white';
                div.style.padding = '15px'; 
                div.style.zIndex = '2147483647';
                div.style.borderRadius = '5px';
                div.style.boxShadow = '0 0 10px rgba(0,0,0,0.5)';
                div.style.textAlign = 'center';
                div.innerHTML = '<b>百度贴吧自动登录助手</b><br>账号: {BAIDU_USER}<br>密码: {BAIDU_PASS}<br><br>请手动完成验证码/短信验证。<br>登录成功后爬虫将自动继续。';
                document.body.appendChild(div);
            }}""")
        except: pass

        print("  [baidutieba] Waiting for login success (Max 120s)...")
        # Wait for login success indicators
        for _ in range(60):
            if page.locator(".u_username_title, .u_username").count() > 0:
                print("  [baidutieba] Login Successful!")
                break
            time.sleep(2)
            
    except Exception as e:
        print(f"  [baidutieba] Login error: {e}")


def scrape_baidutieba(page: Page, url: str, cutoff_date: datetime.datetime, game_key: str):
    # Perform Login first
    login_baidutieba(page)
    
    print(f"  [baidutieba] Scraping {url}...")
    source = "baidutieba"
    
    # Ensure backup dir
    os.makedirs("data", exist_ok=True)
    
    # 1. Access the main list page
    try:
        page.goto(url)
        # Try waiting for the list, if it fails, screenshot
        try:
            page.wait_for_selector("#thread_list", timeout=30000)
        except:
            print("  [baidutieba] #thread_list not found, saving debug_tieba_list.png")
            page.screenshot(path="debug_tieba_list.png")
            # Try finding elements directly
            if page.locator(".j_thread_list").count() > 0:
                print("  [baidutieba] Found .j_thread_list despite timeout on #thread_list")
            else:
                raise Exception("Could not find thread list")
                
    except Exception as e:
        print(f"  [baidutieba] Failed to load list page: {e}")
        return

    # 2. Extract Thread Links
    threads_to_scrape = []
    try:
        # Tieba uses a list item class 'j_thread_list'
        items = page.locator(".j_thread_list").all()
        if not items:
            # Maybe it's the new version or mobile?
            items = page.locator("li[data-field]").all()
            
        for item in items:
            try:
                title_el = item.locator("a.j_th_tit")
                if not title_el.count(): continue
                
                title = title_el.inner_text().strip()
                href = title_el.get_attribute("href")
                
                # Some are top threads (stickies), we might want them or not. 
                # Let's include everything.
                if href:
                    if not href.startswith("http"):
                        full_url = f"https://tieba.baidu.com{href}"
                    else:
                        full_url = href
                    threads_to_scrape.append({"title": title, "url": full_url})
            except: 
                pass
    except Exception as e:
        print(f"  [baidutieba] Error extracting threads: {e}")
    
    print(f"  [baidutieba] Found {len(threads_to_scrape)} threads.")

    # 3. Visit Each Thread
    count_saved = 0
    with open(BACKUP_FILE, "a", encoding="utf-8") as f_backup:
        for i, thread in enumerate(threads_to_scrape):
            t_url = thread['url']
            t_title = thread['title']
            
            print(f"  [baidutieba] ({i+1}/{len(threads_to_scrape)}) Visiting: {t_title[:20]}...")
            
            # Simple rate limiting
            time.sleep(random.uniform(2, 4))
            
            try:
                page.goto(t_url)
                # Wait for post list
                page.wait_for_selector(".l_post", timeout=10000)
                
                # Get all posts
                posts = page.locator(".l_post").all()
                
                for post_idx, post in enumerate(posts):
                    try:
                        # Extract Content
                        content_el = post.locator(".d_post_content").first
                        if not content_el.count(): continue
                        
                        raw_content = content_el.inner_text().strip()
                        if not raw_content: continue
                        
                        # Extract Author
                        author_el = post.locator(".d_name a").first
                        author = author_el.inner_text().strip() if author_el.count() else "Anonymous"
                        
                        # Extract Date
                        # Tieba puts date in .tail-info, usually the last one or 2nd to last
                        date_text = "Unknown"
                        tails = post.locator(".tail-info").all()
                        for tail in tails:
                            txt = tail.inner_text().strip()
                            # Look for date pattern like 2023-11-20 or 2023-11-20 12:30
                            if "-" in txt and ":" in txt:
                                date_text = txt
                                break
                            elif "20" in txt and "-" in txt: # coarse check
                                date_text = txt
                        
                        dt_obj, date_str = parse_date(date_text)
                        
                        # Filter by date
                        if dt_obj and dt_obj < cutoff_date: 
                            # If it's the main post and it's too old, maybe the whole thread is too old?
                            # But Stickies might be old with new replies.
                            # However, replies usually display their own time.
                            continue

                        # Differentiate Main Post (L1) vs Replies
                        content_prefix = "【发帖】" if post_idx == 0 else "【跟帖】"
                        full_content = f"{content_prefix} {raw_content}"
                        
                        # Local Backup
                        record = {
                            "game_key": game_key,
                            "title": t_title,
                            "author": author,
                            "content": full_content,
                            "raw_date": date_text,
                            "parsed_date": date_str,
                            "source": source,
                            "url": t_url,
                            "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                        f_backup.write(json.dumps(record, ensure_ascii=False) + "\n")
                        
                        # Save to DB
                        save_review_helper(
                            game_key=game_key, author=author, content=full_content, rating=0,
                            date_str=date_str, source=source, content_title=t_title, 
                            content_url=t_url, original_date=date_text
                        )
                        count_saved += 1
                        
                    except Exception as e:
                        # print(f"    [baidutieba] Post error: {e}")
                        pass

            except Exception as e:
                print(f"  [baidutieba] Failed to scrape thread {t_url}: {e}")
                
    print(f"  [baidutieba] Done. Saved {count_saved} posts.")
