import time
import random
from core.crawlers.base import parse_date, save_review_helper

def scrape_taptap_intl(page, url, cutoff_date, game_key):
    source = "taptap_intl"
    
    page.goto(url)
    time.sleep(random.uniform(2, 5))
    
    reviews_collected_on_page = 0
    no_change_count = 0
    reached_cutoff = False
    
    # Global/International Selectors
    container_sel = ".post-card"
    date_sel = ".post-card__head-text .tap-time"
    
    while not reached_cutoff:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(2, 4))
        
        review_elements = page.locator(container_sel).all()
        current_count = len(review_elements)
        print(f"  [{source}] Found {current_count} reviews...")
        
        if current_count > 0:
            last_few = review_elements[-5:] 
            for el in last_few:
                date_text = el.locator(date_sel).first.inner_text() if el.locator(date_sel).count() else ""
                dt, _ = parse_date(date_text)
                if dt and dt < cutoff_date:
                    print(f"  Reached old data ({dt.strftime('%Y-%m-%d')}), stopping.")
                    reached_cutoff = True
                    break
        
        if current_count == reviews_collected_on_page:
            no_change_count += 1
            if no_change_count > 5: break
        else:
            no_change_count = 0
            reviews_collected_on_page = current_count
    
    print(f"  Parsing {source}...")
    review_elements = page.locator(container_sel).all()
    
    for el in review_elements:
        try:
            author_sel = ".post-card__head-text span:first-child"
            content_sel = ".post-card__summary"
            
            author_el = el.locator(author_sel).first
            if not author_el.count(): continue
            author = author_el.inner_text().strip()
            
            content_el = el.locator(content_sel).first
            content = content_el.inner_text().strip() if content_el.count() else ""
            
            date_el = el.locator(date_sel).first
            date_text = date_el.inner_text().strip() if date_el.count() else ""
            
            dt_obj, date_str = parse_date(date_text)
            if dt_obj and dt_obj < cutoff_date: continue
            
            # Rating
            rating = 0
            rating_el = el.locator(".rating-star").first
            if rating_el.count():
                 rating = rating_el.locator(".rating-star__item--active").count()
            
            save_review_helper(game_key, author, content, rating, date_str, source, original_date=date_text)
        except Exception as e:
            pass
