import os
import json

GAMES = {
    "jump_assemble": {
        "name": "漫画群星：大集结",
        "url": "https://www.taptap.cn/app/358933/review?os=android",
        "keywords": {
            "孙悟空": "Goku", "悟空": "Goku", "贝吉塔": "Vegeta", "路飞": "Luffy", "索隆": "Zoro",
            "鸣人": "Naruto", "佐助": "Sasuke", "炭治郎": "Tanjiro", "祢豆子": "Nezuko",
            "一护": "Ichigo", "乔巴": "Chopper", "弗利萨": "Frieza", "我爱罗": "Gaara"
        }
    },
    "saint_seiya": {
        "name": "圣斗士星矢：重生2",
        "url": "https://www.taptap.cn/app/507373/review?os=android",
        "keywords": {
            "星矢": "Seiya", "紫龙": "Shiryu", "冰河": "Hyoga", "瞬": "Shun", "一辉": "Ikki",
            "雅典娜": "Athena", "撒加": "Saga", "沙加": "Shaka", "童虎": "Dohko", "哈迪斯": "Hades"
        }
    },
    "slam_dunk": {
        "name": "灌篮高手 正版授权手游",
        "url": "https://www.taptap.cn/app/135988/review?os=android",
        "keywords": {
            "樱木": "Sakuragi", "花道": "Sakuragi", "流川枫": "Rukawa", "流川": "Rukawa",
            "赤木": "Akagi", "三井": "Mitsui", "宫城": "Miyagi", "仙道": "Sendoh", 
            "牧绅一": "Maki", "清田": "Kiyota", "藤真": "Fujima"
        }
    },
    "kuroko": {
        "name": "黑子的篮球 Street Rivals",
        "url": "https://www.taptap.cn/app/739046/review?os=android",
        "keywords": {
            "黑子": "Kuroko", "哲也": "Kuroko", "火神": "Kagami", "大我": "Kagami",
            "黄濑": "Kise", "绿间": "Midorima", "青峰": "Aomine", "紫原": "Murasakibara",
            "赤司": "Akashi"
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
