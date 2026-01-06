import crawler
import analysis
import sys

def main():
    print("Starting Jump Review Monitor System...")
    
    # 1. Crawl
    if "--no-crawl" not in sys.argv:
        print("\n--- Phase 1: Crawling ---")
        try:
            crawler.run_crawler(max_reviews=50) # Small number for demo
        except Exception as e:
            print(f"Crawling failed: {e}")
            # Ask user if they want to continue? No, just proceed if DB has data.
    
    # 2. Analyze
    print("\n--- Phase 2: Analysis ---")
    try:
        analysis.process_reviews()
        analysis.generate_report()
    except Exception as e:
        print(f"Analysis failed: {e}")

if __name__ == "__main__":
    main()
