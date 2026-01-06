import sqlite3
import pandas as pd
from snownlp import SnowNLP
import matplotlib.pyplot as plt
import json
import re
from core.db import get_reviews_for_analysis, update_analysis_results, get_all_data, init_db

# Configure Matplotlib to display Chinese correctly
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# --- Configuration ---

from config.settings import GAMES

# Sub-aspects for Heroes
HERO_DIMENSIONS = {
    "Skill": ["技能", "大招", "被动", "连招", "手感", "前摇", "后摇", "冷却", "CD", "位移"],
    "Visual": ["建模", "皮肤", "立绘", "特效", "形象", "样子", "原画", "丑", "好看"],
    "Strength": ["强", "弱", "刮痧", "超标", "下水道", "伤害", "削", "加强", "数值"]
}

# General Game Aspects
GAME_ASPECTS = {
    "Optimization": ["卡顿", "掉帧", "发热", "闪退", "优化", "在这个手机", "画质", "模糊"],
    "Network": ["460", "延迟", "掉线", "网络", "卡", "红网"],
    "Matchmaking": ["匹配", "人机", "队友", "挂机", "排位", "段位", "炸鱼"],
    "Welfare": ["福利", "氪金", "充值", "活动", "白嫖", "送"]
}

# --- Analysis Functions ---

def analyze_sentiment(text):
    if not text: return 0.5, "Neutral"
    try:
        s = SnowNLP(text)
        score = s.sentiments
        label = "Positive" if score > 0.6 else "Negative" if score < 0.4 else "Neutral"
        return score, label
    except:
        return 0.5, "Neutral"

def extract_keywords(text, game_id="jump_assemble"):
    found = []
    
    # Get keywords for specific game
    game_config = GAMES.get(game_id, GAMES['jump_assemble'])
    hero_map = game_config.get('keywords', {})
    
    # Check Heroes
    for k, v in hero_map.items():
        if k in text:
            if v not in found: found.append(v)
            
    # Check General Aspects
    for k, v in GAME_ASPECTS.items():
        for keyword in v:
            if keyword in text:
                if k not in found: found.append(k)
                break
                
    return json.dumps(found) if found else None

def detailed_aspect_analysis(text, game_id="jump_assemble"):
    analysis = {"Heroes": {}, "System": {}}
    
    game_config = GAMES.get(game_id, GAMES['jump_assemble'])
    hero_map = game_config.get('keywords', {})
    
    clauses = re.split(r'[，。！？;；\n]', text)
    clauses = [c.strip() for c in clauses if c.strip()]
    
    current_hero_context = None
    
    for clause in clauses:
        # Check for Hero Context change
        found_hero = None
        for h_key, h_val in hero_map.items():
            if h_key in clause:
                found_hero = h_val
                break
        
        if found_hero:
            current_hero_context = found_hero
        
        score, label = analyze_sentiment(clause)
        
        # A. Hero Analysis
        if current_hero_context:
            for dim, keywords in HERO_DIMENSIONS.items():
                if any(k in clause for k in keywords):
                    if current_hero_context not in analysis["Heroes"]:
                        analysis["Heroes"][current_hero_context] = {}
                    if dim not in analysis["Heroes"][current_hero_context]:
                        analysis["Heroes"][current_hero_context][dim] = []
                    analysis["Heroes"][current_hero_context][dim].append({
                        "text": clause,
                        "label": label,
                        "score": score
                    })

        # B. System Analysis
        for aspect, keywords in GAME_ASPECTS.items():
            if any(k in clause for k in keywords):
                 if aspect not in analysis["System"]:
                     analysis["System"][aspect] = []
                 analysis["System"][aspect].append({
                     "text": clause,
                     "label": label,
                     "score": score
                 })
                 
    return json.dumps(analysis)

def process_reviews(game_id=None, force=False):
    init_db() 
    print("Fetching reviews for analysis...")
    rows = get_reviews_for_analysis(game_id, force)
    print(f"Found {len(rows)} reviews to process.")
    
    for r in rows:
        rid, content, gid = r
        if not content: continue
        
        # Use the row's game_id if available, otherwise default
        current_gid = gid if gid else (game_id if game_id else "jump_assemble")
        
        score, label = analyze_sentiment(content)
        mentions = extract_keywords(content, current_gid)
        details = detailed_aspect_analysis(content, current_gid)
        
        update_analysis_results(rid, score, label, mentions, details)
        
    print("Analysis update complete.")

def generate_report():
    # Keep the basics, but maybe we can export a JSON of defects?
    df = get_all_data()
    if not df.empty and 'detailed_analysis' in df.columns:
        print("Generating simplified report...")
        # ... (Same old report logic can stay, App.py handles the complex viz)
        pass

if __name__ == "__main__":
    process_reviews()
