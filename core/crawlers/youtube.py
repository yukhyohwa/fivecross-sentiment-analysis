import time
from core.crawlers.base import parse_date, save_review_helper

def scrape_youtube(page, url, cutoff_date, game_key):
    source = "youtube"
    
    # Go to Videos tab if not already there
    if "/videos" not in url:
         if "/@" in url:
            url = url.rstrip('/') + "/videos"
    
    page.goto(url)
    time.sleep(3)
    
def scrape_youtube(page, url, cutoff_date, game_key):
    source = "youtube"
    
    # Go to Videos tab if not already there
    if "/videos" not in url:
         if "/@" in url:
            url = url.rstrip('/') + "/videos"
    
    page.goto(url)
    time.sleep(3)
    
    # 1. Scroll and collect videos until we reach cutoff
    videos_to_scrape = [] # list of dicts: {url, title, date_str}
    
    # Initial scan
    # ytd-rich-grid-media is likely the container for videos in grid view
    # But selector might differ for list view, usually grid view in channel page.
    
    # We need to scroll a bit to get enough history?
    # User said "crawl recently 2 years implemented comments...". 
    # YouTube infinite scroll.
    
    reached_video_cutoff = False
    scroll_attempts = 0
    MAX_SCROLLS = 20 # Safety limit
    
    while not reached_video_cutoff and scroll_attempts < MAX_SCROLLS:
        # Get all visible video items
        # Selector for video item in channel page: ytd-rich-item-renderer
        video_items = page.locator("ytd-rich-item-renderer").all()
        
        # Check the last few items for date
        if video_items:
            # Check the last visible video's date to see if we need to scroll more
            last_item = video_items[-1]
            try:
                # Metadata line: "2.5K views • 1 year ago"
                # it's usually in #metadata-line -> span
                meta_spans = last_item.locator("#metadata-line span").all()
                date_text = ""
                for span in meta_spans:
                    txt = span.inner_text().lower()
                    if "ago" in txt or "前" in txt:
                        date_text = txt
                        break
                
                dt, _ = parse_date(date_text)
                if dt and dt < cutoff_date:
                    print(f"  [{source}] Found old video ({date_text}), stop scrolling.")
                    reached_video_cutoff = True
            except:
                pass
        
        if not reached_video_cutoff:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3)
            scroll_attempts += 1
            
    # 2. Extract Videos to scrape
    # We re-query all items because some might be detached/attached during scroll, 
    # but efficiently we just grab hrefs.
    all_items = page.locator("ytd-rich-item-renderer").all()
    print(f"  [{source}] Found {len(all_items)} total videos on page.")

    for item in all_items:
        try:
            link_el = item.locator("a#video-title-link").first
            title = link_el.get_attribute("title")
            url_suffix = link_el.get_attribute("href")
            
            # Date check again (precise check per item)
            meta_spans = item.locator("#metadata-line span").all()
            date_text = ""
            for span in meta_spans:
                 txt = span.inner_text().lower()
                 if "ago" in txt or "前" in txt:
                     date_text = txt
                     break
            
            dt, _ = parse_date(date_text)
            if dt and dt < cutoff_date:
                continue # Skip this old video
            
            if url_suffix:
                videos_to_scrape.append({
                    "url": "https://www.youtube.com" + url_suffix,
                    "title": title if title else "Unknown",
                    "date": date_text
                })
        except:
             pass
             
    print(f"  [{source}] Scrape target: {len(videos_to_scrape)} videos.")
    
    # 3. Visit each video
    for vid in videos_to_scrape:
        full_url = vid['url']
        vid_title = vid['title']
        print(f"  [{source}] Scraping video: {vid_title} ({full_url})")
        
        try:
            p_vid = page.context.new_page()
            p_vid.goto(full_url)
            time.sleep(3)
            
            # Scroll to comments
            p_vid.evaluate("window.scrollTo(0, 600)")
            time.sleep(2)
            
            # Expand comments
            # Just do a few scrolls for now, or user "last 2 years" implied for comments too?
            # User said "implemented comments... not 3 videos". 
            # I'll stick to a reasonable scroll limit for comments (e.g. 10 pages) or check comment dates?
            # Checking comment dates is safer.
            
            comments_collected = 0
            no_change = 0
            
            for _ in range(10): # Max scroll for comments
                 prev_count = comments_collected
                 p_vid.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                 time.sleep(2)
                 
                 # Check current dates if possible? 
                 # YouTube comment dates are usually relative too.
                 # Let's rely on simple scroll for now to avoid complexity overhead per scroll.
                 
                 curr_count = p_vid.locator("ytd-comment-thread-renderer").count()
                 if curr_count == prev_count:
                     no_change += 1
                     if no_change > 3: break
                 else:
                     no_change = 0
                 comments_collected = curr_count

            comments = p_vid.locator("ytd-comment-thread-renderer").all()
            print(f"    found {len(comments)} comments.")
            
            for comm in comments:
                try:
                    author = comm.locator("#author-text span").first.inner_text().strip()
                    content = comm.locator("#content-text").first.inner_text().strip()
                    time_text = comm.locator("#published-time-text a").first.inner_text().strip()
                    
                    dt, date_str = parse_date(time_text)
                    if not dt: date_str = time_text
                    
                    if dt and dt < cutoff_date: continue
                    
                    if content:
                        save_review_helper(game_key, author, content, 0, date_str, source, 
                                           content_title=vid_title, content_url=full_url, original_date=time_text)
                except:
                    pass
            p_vid.close()
        except Exception as e:
            print(f"    Error scraping video: {e}")
            try: p_vid.close() 
            except: pass
