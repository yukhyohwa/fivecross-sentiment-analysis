import os
import json

GAMES = {
    "jump_assemble": {
        "name": "漫画群星：大集结",
        "urls": [
            "https://www.taptap.cn/app/358933/review?os=android",
            "https://www.taptap.cn/app/358933/review?os=ios",
            "https://www.taptap.io/jp/app/33659119",
            "https://www.youtube.com/@jumpassembletc",
            "https://m-apps.qoo-app.com/en-US/app/31187"
        ],
        "keywords": {
            "孙悟空": "Goku", "悟空": "Goku", "贝吉塔": "Vegeta", "路飞": "Luffy", "索隆": "Zoro",
            "鸣人": "Naruto", "佐助": "Sasuke", "炭治郎": "Tanjiro", "祢豆子": "Nezuko",
            "一护": "Ichigo", "乔巴": "Chopper", "弗利萨": "Frieza", "我爱罗": "Gaara"
        }
    }
}

# --- Dynamic Config Loading ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEROES_CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'heroes.json')

if os.path.exists(HEROES_CONFIG_PATH):
    try:
        with open(HEROES_CONFIG_PATH, 'r', encoding='utf-8') as f:
            dynamic_heroes = json.load(f)
            
        for g_key, g_data in dynamic_heroes.items():
            if g_key in GAMES:
                heroes = g_data.get("Heroes", {})
                for hero_name, aliases in heroes.items():
                    for alias in aliases:
                        GAMES[g_key]["keywords"][alias] = hero_name
    except Exception as e:
        print(f"Error loading dynamic heroes: {e}")
