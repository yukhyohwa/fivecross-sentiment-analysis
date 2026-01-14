import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

GAMES = {
    "jump_assemble": {
        "name": "漫画群星：大集结",
        "crawl_days": 730, # Default 2 years
        "urls": [
            "https://www.taptap.cn/app/358933/review?os=android&sort=new",
            "https://www.taptap.io/tw/app/33659119/review?sort=recent",
            "https://www.youtube.com/@jumpassembletc/videos",
            "https://m-apps.qoo-app.com/app-comment/31187?lang=current&sort=newest",
            "https://forum.gamer.com.tw/B.php?bsn=78752",    # Bahamut Forum
            "https://discord.com/channels/1418135682026704918/1443083478202847232" # Discord
        ],
        "keywords": {
            "孙悟空": "Goku", "悟空": "Goku", "贝吉塔": "Vegeta", "路飞": "Luffy", "索隆": "Zoro",
            "鸣人": "Naruto", "佐助": "Sasuke", "炭治郎": "Tanjiro", "祢豆子": "Nezuko",
            "一护": "Ichigo", "乔巴": "Chopper", "弗利萨": "Frieza", "我爱罗": "Gaara"
        }
    }
}

# --- Credentials ---
BAHAMUT_USER = os.getenv("BAHAMUT_USER", "guest")
BAHAMUT_PASS = os.getenv("BAHAMUT_PASS", "")
DISCORD_USER = os.getenv("DISCORD_USER", "")
DISCORD_PASS = os.getenv("DISCORD_PASS", "")

# --- Dynamic Config Loading ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEROES_CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'heroes.json')

if os.path.exists(HEROES_CONFIG_PATH):
    try:
        with open(HEROES_CONFIG_PATH, 'r', encoding='utf-8') as f:
            dynamic_heroes = json.load(f)
            
        for g_key, g_data in dynamic_heroes.items():
            if g_key in GAMES:
                # Load from "Groups" structure
                if "Groups" in g_data:
                    for group_name, heroes_dict in g_data["Groups"].items():
                        for hero_code, aliases in heroes_dict.items():
                            for alias in aliases:
                                GAMES[g_key]["keywords"][alias] = hero_code
                
                # Fallback for old "Heroes" structure if exists
                if "Heroes" in g_data:
                     for hero_code, aliases in g_data["Heroes"].items():
                        for alias in aliases:
                             GAMES[g_key]["keywords"][alias] = hero_code
                             
        print(f"[DEBUG] Loaded {len(GAMES['jump_assemble']['keywords'])} keywords for jump_assemble.")
        # print(f"[DEBUG] Keywords: {list(GAMES['jump_assemble']['keywords'].keys())[:10]}...")
                             
    except Exception as e:
        print(f"Error loading dynamic heroes: {e}")
