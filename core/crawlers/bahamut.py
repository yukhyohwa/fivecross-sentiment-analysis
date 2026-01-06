from playwright.sync_api import Page
import datetime
import time
from .base import save_review_helper, parse_date

def login_bahamut(page: Page):
    print("  [bahamut] Attempting login...")
    try:
        page.goto("https://user.gamer.com.tw/login.php")
        
        # Wait for form
        try:
            page.wait_for_selector("#userid", timeout=10000)
            print("  [bahamut] Login page loaded.")
        except:
             print("  [bahamut] Login page not detecting inputs. Cloudflare might be blocking.")
             time.sleep(5)
        
        # Fill credentials
        # Check if already logged in? (Usually redirects if logged in, but login.php might stay)
        if page.locator("#userid").count() > 0:
            print("  [bahamut] Filling credentials...")
            page.fill("#userid", "bahauser1y9")
            page.fill("#password", "mt1y9999")
            
            # Click login
            # Usually strict captcha here. We will fill and let user click or try to click.
            # Bahamut often uses a draggable slider or hCaptcha.
            # We will CLICK the button, but if captcha pops up, user needs to solve it.
            
            # Check for 'btn-login'
            if page.locator("#btn-login").count() > 0:
                page.click("#btn-login")
                
            print("  [bahamut] Credentials filled. Please SOLVE CAPTCHA manually if it appears!")
            
            # Wait for login success (redirect to user home or similar)
            # Or just wait for a known cookie "BAHAID"
            # We'll give a generous timeout for manual interaction
            try:
                # Wait until we see the top bar user name or redirected off login page
                page.wait_for_url(lambda u: "login.php" not in u, timeout=60000) 
                print("  [bahamut] Login appeared successful (URL changed).")
            except:
                print("  [bahamut] Warning: Login flow timed out. Continuing anyway...")

    except Exception as e:
        print(f"  [bahamut] Login failed: {e}")

def scrape_bahamut(page: Page, url: str, cutoff_date: datetime.datetime, game_key: str):
    source = "bahamut"
    
    # Perform Login First
    login_bahamut(page)
    
    print(f"  [{source}] Scraping Bahamut Board: {url}")
    
    # 1. Get Thread Links from the list page
    # Bahamut uses specific classes for list items: .b-list__row
    # We want valid threads, not sticky posts or ads if possible, but simpler to filter by date later.
    
    threads_to_scrape = []
    
    try:
        page.goto(url)
        
        # Cloudflare Bypass wait
        try:
           # Try to find the list container. 
           # Note: selector might be .b-list__main (desktop)
           page.wait_for_selector(".b-list__main", timeout=15000)
        except Exception:
           print(f"  [{source}] List not found immediately. Please check browser window.")
           # Give user time to fix
           time.sleep(10)
           if page.title() == "Just a moment...":
               print("    Cloudflare detected. Waiting for manual solve...")
               page.wait_for_selector(".b-list__main", timeout=60000) 
        
        # Iterate through rows
        # Class usually: .b-list__row
        rows = page.locator(".b-list__row").all()
        
        print(f"  [{source}] Found {len(rows)} threads on index page.")
        
        for row in rows:
            try:
                # Extract Title and URL
                # Title selector: .b-list__main__title
                title_el = row.locator(".b-list__main__title")
                if not title_el.count(): continue
                
                title = title_el.inner_text().strip()
                href = title_el.get_attribute("href")
                
                # Check for sticky/announcement? (Usually have specific styles, but we can filter by logic)
                # Let's just grab them.
                
                if href:
                    full_url = f"https://forum.gamer.com.tw/{href}"
                    # Usually urls are relative: C.php?bsn=78752&...
                    if not href.startswith("http"):
                        full_url = f"https://forum.gamer.com.tw/{href}"
                        
                    threads_to_scrape.append({
                        "title": title,
                        "url": full_url
                    })
            except Exception as e:
                pass
                
    except Exception as e:
        print(f"  [{source}] Error loading board index: {e}")
        return

    print(f"  [{source}] identified {len(threads_to_scrape)} threads to scan.")

    # 2. Visit each thread
    for thread in threads_to_scrape:
        t_url = thread['url']
        t_title = thread['title']
        
        print(f"  [{source}] Processing Thread: {t_title}")
        try:
            # Create a new page context ensures clean state, but reusing page is faster usually. 
            # Let's reuse 'page' but handle navigation carefully.
            page.goto(t_url)
            
            # Wait for posts
            # Determine selector for posts. Bahamut uses <section class="c-section" id="post_...">
            page.wait_for_selector("section.c-section", timeout=5000)
            
            posts = page.locator("section.c-section").all()
            
            for post in posts:
                try:
                    # Author
                    # .c-user__name
                    author_el = post.locator(".c-user__name")
                    if not author_el.count(): continue
                    author = author_el.inner_text().strip()
                    
                    # Content
                    # .c-article__content
                    content_el = post.locator(".c-article__content")
                    if not content_el.count(): continue
                    content = content_el.inner_text().strip()
                    
                    # Date
                    # .edittime (editing time) or .c-post__header__info (floor info)?
                    # Usually there is a data attribute or text.
                    # .edittime example: "2024-01-01 12:00:00"
                    # Or specific post time element.
                    # Use .c-post__header data-mtime or similar if hard to find text. 
                    # Let's try to find the clean text date.
                    # Element: .c-post__header .edittime (sometimes hidden) or just the last span in header?
                    # Bahamut desktop view: header has a link with data-href and text date.
                    
                    # Fallback text locator for date
                    date_el = post.locator(".c-post__header a[data-href]").first
                    if date_el.count():
                        date_text = date_el.inner_text().strip()
                    else:
                        # Mobile/Responsive might be different.
                        # Look for any text looking like date in header
                        header_text = post.locator(".c-post__header").inner_text()
                        # Extract YYYY-MM-DD from header text simply
                        import re
                        match = re.search(r'\d{4}-\d{2}-\d{2}', header_text)
                        date_text = match.group(0) if match else "Unknown"
                        
                    # Parse Date
                    # Bahamut date format is usually YYYY-MM-DD HH:MM:SS
                    dt, date_str = parse_date(date_text)
                    
                    # Check cutoff
                    if dt and dt < cutoff_date:
                        # If meaningful optimization needed: if Main Post is old, maybe stop?
                        # But replies can be new. So we process all on page 1.
                        continue
                        
                    # Save
                    # Reuse video_title for Thread Title, video_url for Thread URL
                    save_review_helper(
                        game_key=game_key,
                        author=author,
                        content=content,
                        rating=0, # Forums don't have star ratings
                        date_str=date_str,
                        source=source,
                        video_title=t_title, 
                        video_url=t_url,
                        original_date=date_text
                    )
                    
                except Exception as e:
                    # print(f"    Error parsing post: {e}")
                    pass
                    
        except Exception as e:
            print(f"  [{source}] Error processing thread {t_url}: {e}")
