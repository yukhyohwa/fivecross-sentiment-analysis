from playwright.sync_api import Page
import datetime
import time
from .base import save_review_helper, parse_date

def scrape_bahamut(page: Page, url: str, cutoff_date: datetime.datetime, game_key: str):
    source = "bahamut"
    print(f"  [{source}] Scraping Bahamut Board: {url}")
    
    # 1. Get Thread Links from the list page
    # Bahamut uses specific classes for list items: .b-list__row
    # We want valid threads, not sticky posts or ads if possible, but simpler to filter by date later.
    
    threads_to_scrape = []
    
    try:
        page.goto(url)
        
        # Cloudflare Bypass Wait
        # Wait up to 30 seconds for the user to solve captcha if needed
        print(f"  [{source}] Waiting for page load... (Please solve Cloudflare captcha if it appears)")
        try:
           page.wait_for_selector(".b-list__main", timeout=30000)
        except Exception:
           print(f"  [{source}] Timeout waiting for list directly. Checking if blocked...")
           # Maybe pause longer?
           time.sleep(5)
           if page.title() == "Just a moment...":
               print(f"  [{source}] Cloudflare detected! Please verify manually in the browser!")
               page.wait_for_selector(".b-list__main", timeout=60000) # Give 60s more for manual solve
        
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
