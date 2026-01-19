
import sys
import os
import subprocess
import argparse

# Ensure core modules can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.analysis import process_reviews
from core.crawler import run_crawler
from core.generate_sentiment_report import generate_report

def run_web_ui():
    print("Starting Web UI...")

    # Use absolute path so it works from any directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(base_dir, "app", "web_ui.py")
    subprocess.run([sys.executable, "-m", "streamlit", "run", app_path])

def start_interactive_menu():
    while True:
        print("\n=== FiveCross Sentiment Analysis CLI ===")
        print("1. Run Web UI (Visual Dashboard)")
        print("2. Run Crawler (Fetch new data)")
        print("3. Run Analysis (Process NLP on existing data)")
        print("4. Generate Analysis Report (Update Monthly Report)")
        print("5. Exit")
        
        choice = input("\nEnter choice [1-5]: ").strip()
        
        if choice == '1':
            run_web_ui()
        elif choice == '2':
            print("\n--- Crawler ---")
            game_key = input("Enter game key [default: jump_assemble]: ").strip() or "jump_assemble"
            days = input("Enter days back [default: 30]: ").strip() or "30"
            run_crawler(game_key, int(days))
        elif choice == '3':
            print("\n--- Analysis ---")
            game_key = input("Enter game key [default: jump_assemble]: ").strip() or "jump_assemble"
            process_reviews(game_key)
        elif choice == '4':
            print("\n--- Generating Report ---")
            generate_report()
            print("Report sync complete.")
        elif choice == '5':
            print("Exiting.")
            sys.exit(0)
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sentiment Analysis Tool Entry Point")
    parser.add_argument("mode", nargs="?", help="Mode: web, crawl, analyze, report")
    parser.add_argument("--game", default="jump_assemble", help="Game ID for crawl/analyze")
    parser.add_argument("--days", default=None, type=int, help="Days history for crawler (overrides settings)")
    parser.add_argument("--source", default=None, help="Filter crawler by source URL (e.g., 'bahamut', 'youtube')")
    parser.add_argument("--force", action="store_true", help="Force re-analysis of all data")

    args = parser.parse_args()
    
    if args.mode == "web":
        run_web_ui()
    elif args.mode == "crawl":
        run_crawler(args.game, days_back=args.days, source_filter=args.source)
    elif args.mode == "analyze":
        process_reviews(args.game, force=args.force)
        print("Updating monthly report...")
        generate_report()
    elif args.mode == "report":
        generate_report()
    else:
        start_interactive_menu()
