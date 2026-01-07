import re
import json
import sqlite3
import datetime
import os
from config.settings import GAMES
from snownlp import SnowNLP

# Specific emotions for Gemini tagging (Schema extension placeholder)
EMOTION_CHANNELS = ["anger", "disappointment", "expectation", "surprise", "sarcasm", "gratitude"]

# Gameplay Modes (These will be Tags/Badges)
GAME_MODES = {
    "PVP": ["PVP", "竞技", "競技", "对抗", "對抗", "ranked", "competitive"],
    "PVE": ["PVE", "刷图", "刷圖", "副本", "剧情", "劇情", "关卡", "關卡", "冒险", "冒險", "story", "adventure", "stage", "mission"],
    "3v3": ["3v3", "3对3", "3對3", "小乱斗", "小亂鬥", "三对三", "三對三"],
    "5v5": ["5v5", "5对5", "5對5", "大集结", "大集結", "匹配赛", "五对五", "五對五", "main mode"],
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
    "Visual": ["建模", "皮肤", "皮膚", "立绘", "立繪", "特效", "形象", "颜值", "颜控", "顏值", "好看", "帅", "帥", "美", "丑", "醜", "动画", "動畫", "还原", "還原", "design", "visual", "skin", "art", "graphic", "model", "cool"],
    "Strength": ["强", "強", "弱", "刮痧", "超标", "下水道", "伤害", "傷害", "削", "砍", "加强", "加強", "数值怪", "强度", "強度", "厉害", "厲害", "平衡", "T0", "T1", "好用", "猛", "爆发", "控制", "meta", "tier", "strong", "broken", "nerf", "buff", "damage", "op", "tier", "powerful"]
}

# General Game Aspects
GAME_ASPECTS = {
    "Optimization": ["卡顿", "卡頓", "掉帧", "掉幀", "发热", "發熱", "闪退", "閃退", "优化", "優化", "画质", "畫質", "流畅", "流暢", "fps", "lag", "crash", "stutter", "optimization", "graphics", "performance"],
    "Network": ["460", "延迟", "延遲", "掉线", "斷線", "网络", "網絡", "網路", "卡", "ping", "net", "network", "server", "disconnect"],
    "Matchmaking": ["匹配", "人机", "人機", "队友", "隊友", "挂机", "掛機", "演员", "連敗", "连败", "連勝", "连胜", "ELO", "排位", "段位", "天梯", "上分", "matchmaking", "teammate", "afk", "rank", "elo", "noob"],
    "Welfare": ["福利", "氪金", "充值", "活动", "活動", "白嫖", "送", "抽奖", "抽獎", "价格", "價格", "贵", "貴", "坑", "良心", "首充", "任务", "任務", "event", "welfare", "free", "price", "pay", "money", "shop", "gacha", "cheap"]
}

def analyze_sentiment(text):
    if not text or not text.strip():
        return 0.5, "Neutral"

    # 1. Start with SnowNLP for Chinese content
    score = 0.5
    try:
        if re.search(r'[\u4e00-\u9fa5]', text):
            score = SnowNLP(text).sentiments
    except:
        pass

    # 2. Apply rule-based bias for game-specific sentiment (More sensitive)
    pos_words = ["好", "赞", "贊", "强", "強", "不错", "不錯", "神", "神作", "优秀", "还原", "流畅", "良心", "爽", "喜欢", "期待", "好用", "还原度"]
    neg_words = ["烂", "爛", "差", "负面", "失望", "废", "难", "坑", "垃圾", "卡", "慢", "贵", "恶心", "辣鸡", "丑", "弱", "削", "砍", "不听话"]
    
    for w in pos_words:
        if w in text: score += 0.1
    for w in neg_words:
        if w in text: score -= 0.1
    
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

def detailed_aspect_analysis(text, game_id="jump_assemble"):
    analysis = {"Heroes": {}, "System": {}}
    game_config = GAMES.get(game_id, GAMES['jump_assemble'])
    hero_map = game_config.get('keywords', {})
    
    clauses = re.split(r'[，。！？;；\n,.!?]', text)
    clauses = [c.strip() for c in clauses if c.strip()]
    
    current_hero_context = None
    
    for clause in clauses:
        found_heroes_in_clause = []
        for h_key, h_val in hero_map.items():
            if h_key in clause:
                if h_val not in found_heroes_in_clause:
                    found_heroes_in_clause.append(h_val)
        
        if found_heroes_in_clause:
            current_hero_context = found_heroes_in_clause
            
        score, label = analyze_sentiment(clause)
        
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
                            "text": clause, "label": label, "score": score
                        })
                        matched_dim = True
                        break
                
                if not matched_dim:
                    if hero_code not in analysis["Heroes"]:
                        analysis["Heroes"][hero_code] = {}
                    if "General" not in analysis["Heroes"][hero_code]:
                        analysis["Heroes"][hero_code]["General"] = []
                    analysis["Heroes"][hero_code]["General"].append({
                        "text": clause, "label": label, "score": score
                    })

        for aspect, keywords in GAME_ASPECTS.items():
            if any(k in clause.lower() for k in keywords):
                 if aspect not in analysis["System"]:
                     analysis["System"][aspect] = []
                 
                 tags = []
                 for mode, mode_keywords in GAME_MODES.items():
                     if any(mk in clause.lower() for mk in mode_keywords):
                         tags.append(mode)
                         
                 analysis["System"][aspect].append({
                     "text": clause, "label": label, "score": score, "tags": tags
                 })
                 
    return json.dumps(analysis, ensure_ascii=False)

def process_reviews(game_id=None, force=False):
    from core.db import init_db, get_reviews_for_analysis, update_analysis_results
    init_db() 
    rows = get_reviews_for_analysis(game_id, force)
    print(f"Analyzing {len(rows)} reviews...")
    for r in rows:
        rid, content, gid = r
        if not content: continue
        current_gid = gid if gid else (game_id if game_id else "jump_assemble")
        score, label = analyze_sentiment(content)
        details = detailed_aspect_analysis(content, current_gid)
        update_analysis_results(rid, score, label, None, details)
    print("Analysis complete.")
