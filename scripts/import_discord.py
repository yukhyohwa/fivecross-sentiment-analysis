
import sys
import os

# Add root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils.discord_helper import import_discord_files

if __name__ == "__main__":
    print("=== Discord Manual Data Importer ===")
    import_discord_files()
    print("Done.")
