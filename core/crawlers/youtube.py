import time
import json
import os
from core.crawlers.base import parse_date, save_review_helper

BACKUP_FILE = "data/backups/youtube_backup.jsonl"

def scrape_youtube(page, url, cutoff_date, game_key):
    source = "youtube"
    
    # Ensure backup dir
    os.makedirs("data/backups", exist_ok=True)
    
    # Go to Videos tab if not already there
    if "/videos" not in url:
         if "/@" in url:
            url = url.rstrip('/') + "/videos"
    
    page.goto(url)
    time.sleep(3)
    
    # 1. Scroll and collect videos until we reach cutoff
    videos_to_scrape = [] # list of dicts: {url, title, date_str}
    
    reached_video_cutoff = False
    scroll_attempts = 0
    MAX_SCROLLS = 20 # Safety limit
    
    while not reached_video_cutoff and scroll_attempts < MAX_SCROLLS:
        video_items = page.locator("ytd-rich-item-renderer").all()
        
        if video_items:
            last_item = video_items[-1]
            try:
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
    all_items = page.locator("ytd-rich-item-renderer").all()
    print(f"  [{source}] Found {len(all_items)} total videos on page.")

    for item in all_items:
        try:
            link_el = item.locator("a#video-title-link").first
            title = link_el.get_attribute("title")
            url_suffix = link_el.get_attribute("href")
            
            meta_spans = item.locator("#metadata-line span").all()
            date_text = ""
            for span in meta_spans:
                 txt = span.inner_text().lower()
                 if "ago" in txt or "前" in txt:
                     date_text = txt
                     break
            
            dt, _ = parse_date(date_text)
            if dt and dt < cutoff_date:
                continue
            
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
    with open(BACKUP_FILE, "a", encoding="utf-8") as f_backup:
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
                
                comments_collected = 0
                no_change = 0
                
                for _ in range(10): # Max scroll for comments
                     prev_count = comments_collected
                     p_vid.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                     time.sleep(2)
                     
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
                        author_el = comm.locator("#author-text span").first
                        if not author_el.count(): continue
                        author = author_el.inner_text().strip()
                        
                        content_el = comm.locator("#content-text").first
                        content = content_el.inner_text().strip() if content_el.count() else ""
                        
                        time_el = comm.locator("#published-time-text a").first
                        time_text = time_el.inner_text().strip() if time_el.count() else ""
                        
                        dt, date_str = parse_date(time_text)
                        if not dt: date_str = time_text
                        
                        if dt and dt < cutoff_date: continue
                        
                        if content:
                            # Local Backup
                            record = {
                                "game_key": game_key,
                                "video_title": vid_title,
                                "author": author,
                                "content": content,
                                "raw_date": time_text,
                                "parsed_date": date_str,
                                "source": source,
                                "url": full_url,
                                "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S")
                            }
                            f_backup.write(json.dumps(record, ensure_ascii=False) + "\n")
                            
                            save_review_helper(game_key, author, content, 0, date_str, source, 
                                               content_title=vid_title, content_url=full_url, original_date=time_text)
                    except:
                        pass
                p_vid.close()
            except Exception as e:
                print(f"    Error scraping video: {e}")
                try: p_vid.close() 
                except: pass
    print(f"  [{source}] Done. Local backup at {BACKUP_FILE}")
