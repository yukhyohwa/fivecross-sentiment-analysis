import re
import json
import sqlite3
import datetime
import os
from config.settings import GAMES
from snownlp import SnowNLP
import nltk
from nltk.stem import WordNetLemmatizer
try:
    from pythainlp import word_tokenize as thai_tokenize
    nltk.download('wordnet', quiet=True)
    lemmatizer = WordNetLemmatizer()
    HAS_SPECIALIZED = True
except ImportError:
    HAS_SPECIALIZED = False

# Specific emotions for Gemini tagging (Schema extension placeholder)
EMOTION_CHANNELS = ["anger", "disappointment", "expectation", "surprise", "sarcasm", "gratitude"]

# Gameplay Modes (These will be Tags/Badges)
GAME_MODES = {
    "PVP": ["PVP", "竞技", "競技", "对抗", "對抗", "ranked", "competitive"],
    "PVE": ["PVE", "刷图", "刷圖", "副本", "剧情", "劇情", "关卡", "關卡", "冒险", "冒險", "story", "adventure", "stage", "mission"],
    "3v3": ["3v3", "3V3", "3对3", "3對3", "小乱斗", "小亂鬥", "三对三", "三對三"],
    "5v5": ["5v5", "5V5", "MOBA", "moba", "5对5", "5對5", "大集结", "大集結", "匹配赛", "五对五", "五對五", "main mode"],
    "积分赛": ["积分争夺", "積分爭奪", "积分赛", "積分賽", "资源争夺", "資源爭奪"],
    "顶上战争": ["顶上战争", "頂上之戰", "顶上", "頂上", "大乱斗", "大亂鬥", "summit", "war"],
    "卷轴争夺": ["卷轴争夺", "卷軸爭奪", "卷轴", "卷軸", "scroll"],
    "无限列车": ["无限列车", "無限列車", "列车", "列車", "train", "mugen"],
    "咒术高专": ["咒术高专", "咒術高專", "高专", "高專", "jjk school", "academy"],
    "武道会": ["武道会", "武道會", "天下第一", "budokai", "tournament"],
    "双人乱斗": ["双人乱斗", "雙人亂鬥", "双人", "雙人", "duo brawl", "duo"],
    "单人乱斗": ["单人乱斗", "單人亂鬥", "单人", "單人", "solo brawl", "solo"]
}


# Sub-aspects for Heroes
HERO_DIMENSIONS = {
    "Skill": ["技能", "大招", "被动", "連招", "連段", "手感", "冷却", "CD", "位移", "手速", "操作", "机制", "招式", "招数", "能力", "skill", "ability", "ultimate", "passive", "mechanic", "technical", "difficult"],
    "Visual": ["建模", "皮肤", "皮膚", "立绘", "立繪", "特效", "形象", "颜值", "颜控", "顏值", "好看", "帅", "帥", "美", "丑", "醜", "动画", "動畫", "还原", "還原", "design", "visual", "skin", "art", "graphic", "model", "cool", "外貌", "长相", "长得", "造型", "气质", "脸型", "脸蛋", "精美", "细节", "画风", "风格", "画质", "建模师", "出场", "展示", "配音", "CV", "声音", "台词", "原画", "崩了", "拉胯", "僵硬", "逼真", "震撼", "华丽", "色彩", "比例", "审美", "高大上"],
    "Strength": ["强", "強", "弱", "刮痧", "超标", "下水道", "伤害", "傷害", "削", "砍", "加强", "加強", "数值怪", "强度", "強度", "厉害", "厲害", "平衡", "T0", "T1", "好用", "猛", "爆发", "控制", "meta", "tier", "strong", "broken", "nerf", "buff", "damage", "op", "tier", "powerful"]
}

# General Game Aspects
GAME_ASPECTS = {
    "Optimization": ["卡顿", "卡頓", "掉帧", "掉幀", "发热", "發熱", "闪退", "閃退", "优化", "優化", "画质", "畫質", "流畅", "流暢", "fps", "lag", "crash", "stutter", "optimization", "graphics", "performance"],
    "Network": ["460", "延迟", "延遲", "掉线", "斷線", "网络", "網絡", "網路", "卡", "ping", "net", "network", "server", "disconnect"],
    "Matchmaking": ["匹配", "人机", "人機", "队友", "隊友", "挂机", "掛機", "演员", "連敗", "连败", "連勝", "连胜", "ELO", "排位", "段位", "天梯", "上分", "matchmaking", "teammate", "afk", "rank", "elo", "noob"],
    "Welfare": ["福利", "氪金", "充值", "活动", "活動", "白嫖", "送", "抽奖", "抽獎", "价格", "價格", "贵", "貴", "坑", "良心", "首充", "任务", "任務", "event", "welfare", "free", "price", "pay", "money", "shop", "gacha", "cheap"],
    "Gameplay": ["手感", "打击感", "打擊感", "平衡", "机制", "機制", "玩法", "操作", "判定", "balance", "gameplay", "controls", "mechanic", "mode", "fun", "boring", "MOBA"],
    "Visuals": ["还原", "還原", "画质", "畫質", "建模", "立绘", "立繪", "特效", "ui", "界面", "graphic", "visual", "art", "design", "model"]
}

def analyze_sentiment(text):
    if not text or not text.strip():
        return 0.5, "Neutral"

    # 0. Official Pattern Detection (Forced Neutral)
    official_phrases = ["頻道守則", "意見回饋", "營運團隊", "勾选建议类别", "勾選建議類別", "遵守【頻道守則】"]
    if any(phrase in text for phrase in official_phrases):
        return 0.5, "Neutral"

    # 1. Start with SnowNLP for Chinese content
    score = 0.5
    try:
        if re.search(r'[\u4e00-\u9fa5]', text):
            score = SnowNLP(text).sentiments
    except:
        pass

    # 2. Apply rule-based bias for game-specific sentiment (More sensitive)
    pos_words = ["好", "赞", "贊", "强", "強", "不错", "不錯", "神", "神作", "优秀", "还原", "流畅", "良心", "爽", "喜欢", "期待", "好用", "还原度", "精美", "丝滑"]
    neg_words = [
        "烂", "爛", "差", "负面", "失望", "废", "难", "坑", "垃圾", "卡", "慢", "贵", "恶心", "辣鸡", "丑", "弱", "削", "砍", 
        "不听话", "贵得要死", "贵死", "吃相难看", "离谱", "滚", "没诚意", "割韭菜",
        "一坨", "稀碎", "稀烂", "拉胯", "拉垮", "不好", "不行", "僵硬", "笨重", "拉稀", "毁", "崩", "劝退",
        "傻逼", "SB", "脑残", "孤儿", "寄了", "凉了", "卸载", "删游戏", "退钱", "骗氪", "暗改", "差评", "给一星",
        "垃圾平衡", "平衡烂", "匹配烂", "人机多", "恶性bug", "滚出", "糟蹋", "毁原作", "没救了", "玩你妈",
        "傻X", "sb", "垃圾公司", "避雷", "快逃", "千万别玩", "浪费时间", "什么玩意", "玩不下去"
    ]
    
    # Strong negatives that should heavily weight the score
    strong_negatives = [
        "贵得要死", "太贵", "吃相难看", "垃圾", "烂", "烂作", "割韭菜", "稀烂", "稀碎", "一坨", "狗屎", "答辩",
        "傻逼", "SB", "脑残", "给一星", "退钱", "孤儿", "玩你妈", "垃圾公司", "喂屎", "差到极致", "千万别玩"
    ]
    
    for w in pos_words:
        # Special handling: Don't count "好" if "不好" or "不怎么好" or "不太好" is present
        if w == "好" and any(neg in text for neg in ["不好", "不太好", "不怎么好", "好卡", "好难"]):
            continue
        if w in text: score += 0.15
    for w in neg_words:
        if w in text: score -= 0.15
    for w in strong_negatives:
        if w in text: score -= 0.25 # Additional penalty
    
    # 3. Handle English Rule-based if no Chinese
    if not re.search(r'[\u4e00-\u9fa5]', text):
        en_pos = ["good", "great", "nice", "love", "awesome", "amazing", "fun", "best", "buff", "strong"]
        en_neg = ["bad", "worst", "hate", "trash", "rubbish", "boring", "toxic", "laggy", "expensive", "nerf", "weak"]
        for w in en_pos:
            if w in text.lower(): score += 0.1
        for w in en_neg:
            if w in text.lower(): score -= 0.1

    score = max(0.0, min(1.0, score))
    
    # 4. Standard Labels (Clearer thresholds)
    if score > 0.51:
        label = "Positive"
    elif score < 0.49:
        label = "Negative"
    else:
        label = "Neutral"
        
    return round(score, 3), label

def load_hero_map(game_id):
    # Flatten: Groups -> Series -> Hero -> Aliases
    # Returns {alias: hero_code}
    hero_map = {}
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        heroes_path = os.path.join(base_dir, 'config', 'heroes.json')
        
        if os.path.exists(heroes_path):
            with open(heroes_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                game_data = data.get(game_id, {})
                groups = game_data.get('Groups', {})
                for group_name, heroes in groups.items():
                    for hero_code, aliases in heroes.items():
                        for alias in aliases:
                            hero_map[alias] = hero_code
    except Exception as e:
        print(f"Error loading hero map: {e}")
        
    return hero_map

def detailed_aspect_analysis(text, game_id="jump_assemble", metadata=None):
    """
    metadata: optional dict containing 'source', 'date', 'full_content'
    """
    analysis = {"Heroes": {}, "System": {}}
    
    # Use the new robust loader
    hero_map = load_hero_map(game_id)
    
    clauses = re.split(r'[，。！？;；\n,.!?]', text)
    clauses = [c.strip() for c in clauses if c.strip()]
    
    current_hero_context = None
    
    for clause in clauses:
        found_heroes_in_clause = []
        for h_alias, h_code in hero_map.items():
            if h_alias in clause:
                if h_code not in found_heroes_in_clause:
                    found_heroes_in_clause.append(h_code)
        
        if found_heroes_in_clause:
            current_hero_context = found_heroes_in_clause
            
        score, label = analyze_sentiment(clause)
        
        # 1. Hero Analysis
        if current_hero_context:
            for hero_code in current_hero_context:
                matched_dim = False
                for dim, kw_list in HERO_DIMENSIONS.items():
                    if any(k in clause.lower() for k in kw_list):
                        if hero_code not in analysis["Heroes"]:
                            analysis["Heroes"][hero_code] = {}
                        if dim not in analysis["Heroes"][hero_code]:
                            analysis["Heroes"][hero_code][dim] = []
                        analysis["Heroes"][hero_code][dim].append({
                            "text": clause, 
                            "label": label, 
                            "score": score,
                            "metadata": metadata
                        })
                        matched_dim = True
                        break
                
                if not matched_dim:
                    if hero_code not in analysis["Heroes"]:
                        analysis["Heroes"][hero_code] = {}
                    if "General" not in analysis["Heroes"][hero_code]:
                        analysis["Heroes"][hero_code]["General"] = []
                    analysis["Heroes"][hero_code]["General"].append({
                        "text": clause, 
                        "label": label, 
                        "score": score,
                        "metadata": metadata
                    })

    # 2. System Aspect Analysis (Iterate clauses again vs Aspects)
    for aspect, keywords in GAME_ASPECTS.items():
        for clause in clauses:
            match_found = False
            # Smart matching
            if re.search(r'[\u0E00-\u0E7F]', clause) and HAS_SPECIALIZED:
                tokens = thai_tokenize(clause, engine="newmm")
                if any(k in tokens for k in keywords): match_found = True
            elif not re.search(r'[\u4e00-\u9fa5]', clause) and HAS_SPECIALIZED:
                tokens = [lemmatizer.lemmatize(w.lower()) for w in re.findall(r'\b[a-z]{2,}\b', clause)]
                if any(lemmatizer.lemmatize(k.lower()) in tokens for k in keywords): match_found = True
            else:
                if any(k in clause.lower() for k in keywords): match_found = True

            if match_found:
                 score, label = analyze_sentiment(clause) 
                 if aspect not in analysis["System"]:
                     analysis["System"][aspect] = []
                 
                 tags = []
                 for mode, mode_keywords in GAME_MODES.items():
                     if any(mk in clause.lower() for mk in mode_keywords):
                         tags.append(mode)
                         
                 analysis["System"][aspect].append({
                     "text": clause, 
                     "label": label, 
                     "score": score, 
                     "tags": tags,
                     "metadata": metadata
                 })
                 
    return json.dumps(analysis, ensure_ascii=False)

def process_reviews(game_id=None, force=False):
    from core.db import init_db, get_reviews_for_analysis, update_analysis_results
    init_db() 
    rows = get_reviews_for_analysis(game_id, force)
    print(f"Analyzing {len(rows)} reviews...")
    for r in rows:
        rid, content, gid, source, date = r
        if not content: continue
        current_gid = gid if gid else (game_id if game_id else "jump_assemble")
        
        metadata = {
            "source": source,
            "date": date,
            "full_content": content
        }
        
        official_authors = ["JUMP : 群星集結", "@JUMP : 群星集結"]
        if len(r) > 2 and any(oa in str(r[2]) for oa in official_authors):
            score, label = 0.5, "Neutral"
        else:
            score, label = analyze_sentiment(content)
            
        details_json = detailed_aspect_analysis(content, current_gid, metadata=metadata)
        
        # Extract identified heroes
        try:
            details = json.loads(details_json)
            heroes_found = list(details.get("Heroes", {}).keys())
            char_mentions_str = ",".join(heroes_found) if heroes_found else None
        except:
            char_mentions_str = None
            
        update_analysis_results(rid, score, label, char_mentions_str, details_json)
    print("Analysis complete.")
