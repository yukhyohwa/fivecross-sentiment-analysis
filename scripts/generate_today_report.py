
import sqlite3
import pandas as pd
import json
import collections
import jieba
import os
import re
import datetime
import sys

# Project root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from core.generate_sentiment_report import load_stopwords, DB_PATH, CHAT_DB_PATH

# Set date to today
TODAY = "2026-04-15"

def load_today_data():
    """Unify data from reviews and chat messages for today."""
    
    # 1. Load Reviews
    conn_r = sqlite3.connect(DB_PATH)
    query_r = f"SELECT * FROM reviews WHERE review_date LIKE '{TODAY}%'"
    df_r = pd.read_sql_query(query_r, conn_r)
    conn_r.close()
    
    # 2. Load Chats
    df_c = pd.DataFrame()
    if os.path.exists(CHAT_DB_PATH):
        conn_c = sqlite3.connect(CHAT_DB_PATH)
        query_c = f"SELECT * FROM chat_messages WHERE message_date LIKE '{TODAY}%'"
        try:
            df_c = pd.read_sql_query(query_c, conn_c)
            if not df_c.empty:
                # Standardize columns
                if 'message_date' in df_c.columns:
                    df_c = df_c.rename(columns={'message_date': 'review_date'})
                if 'rating' not in df_c.columns:
                    df_c['rating'] = 0 
        except: pass
        conn_c.close()
    
    if df_r.empty and df_c.empty:
        return pd.DataFrame()
        
    return pd.concat([df_r, df_c], ignore_index=True, sort=False)

def generate_today_report():
    df = load_today_data()

    if df.empty:
        print(f"No data found for {TODAY}")
        return

    # Basic stats
    total_reviews = len(df)
    avg_sentiment = df['sentiment_score'].mean()
    sentiment_counts = df['sentiment_label'].value_counts().to_dict()

    aspect_feedback = {}
    hero_feedback = {}

    for _, row in df.iterrows():
        if pd.isna(row['detailed_analysis']): continue
        try:
            analysis = json.loads(row['detailed_analysis'])
            system = analysis.get("System", {})
            for aspect, items in system.items():
                if aspect not in aspect_feedback:
                    aspect_feedback[aspect] = {"pos": 0, "neg": 0, "neutral": 0, "total": 0}
                for item in items:
                    label = item['label'].lower()
                    if label == 'positive': aspect_feedback[aspect]["pos"] += 1
                    elif label == 'negative': aspect_feedback[aspect]["neg"] += 1
                    else: aspect_feedback[aspect]["neutral"] += 1
                    aspect_feedback[aspect]["total"] += 1

            heroes = analysis.get("Heroes", {})
            for hero, dims in heroes.items():
                if hero not in hero_feedback:
                    hero_feedback[hero] = {"pos": 0, "neg": 0, "neutral": 0, "total": 0}
                for dim, items in dims.items():
                    for item in items:
                        label = item['label'].lower()
                        if label == 'positive': hero_feedback[hero]["pos"] += 1
                        elif label == 'negative': hero_feedback[hero]["neg"] += 1
                        else: hero_feedback[hero]["neutral"] += 1
                        hero_feedback[hero]["total"] += 1
        except: continue

    # Word Frequency
    stopwords = load_stopwords()
    all_words = []
    for txt in df['content'].dropna():
        words = [w for w in jieba.cut(str(txt)) if len(w) > 1 and w not in stopwords and not re.match(r'^[0-9.]+$', w)]
        all_words.extend(words)
    word_freq = collections.Counter(all_words).most_common(20)

    neg_reviews = df[df['sentiment_label'] == 'Negative'].sort_values(by='sentiment_score').head(10)['content'].tolist()
    source_counts = df['source'].value_counts().to_dict()

    report = f"# 《漫画群星：大集结》今日舆情监测報告 ({TODAY})\n\n"
    report += f"**發生日期**: {TODAY}\n"
    report += f"**生成時間**: {pd.Timestamp.now().strftime('%H:%M')}\n\n"

    report += "## 一、 今日輿情概況\n"
    report += f"- **總採集樣本數**: {total_reviews} 條\n"
    report += f"- **今日整體情感平均分**: {avg_sentiment:.2f}\n"
    report += "  - **正面 (Positive)**: " + str(sentiment_counts.get('Positive', 0)) + "\n"
    report += "  - **負面 (Negative)**: " + str(sentiment_counts.get('Negative', 0)) + "\n"
    report += "  - **中立 (Neutral)**: " + str(sentiment_counts.get('Neutral', 0)) + "\n\n"

    report += "## 二、 渠道分布\n"
    for source, count in source_counts.items():
        report += f"- **{source}**: {count} 條\n"
    report += "\n"

    report += "## 三、 今日核心話題 (System Aspects)\n"
    report += "| 話題維度 | 次數 | 正面 | 負面 | 正向率 |\n"
    report += "| :--- | :--- | :--- | :--- | :--- |\n"
    for aspect, stats in sorted(aspect_feedback.items(), key=lambda x: x[1]['total'], reverse=True):
        pos_rate = (stats['pos'] / stats['total'] * 100) if stats['total'] > 0 else 0
        report += f"| {aspect} | {stats['total']} | {stats['pos']} | {stats['neg']} | {pos_rate:.1f}% |\n"
    report += "\n"

    report += "## 四、 今日英雄反饋 (Top 10)\n"
    report += "| 英雄代號 | 次數 | 正面 | 負面 | 正向率 |\n"
    report += "| :--- | :--- | :--- | :--- | :--- |\n"
    for hero, stats in sorted(hero_feedback.items(), key=lambda x: x[1]['total'], reverse=True)[:10]:
        pos_rate = (stats['pos'] / stats['total'] * 100) if stats['total'] > 0 else 0
        report += f"| {hero} | {stats['total']} | {stats['pos']} | {stats['neg']} | {pos_rate:.1f}% |\n"
    report += "\n"

    report += "## 五、 關注焦點 (今日關鍵詞)\n"
    report += ", ".join([f"{word}({count})" for word, count in word_freq])
    report += "\n\n"

    if 'cluster_label' in df.columns:
        report += "## 六、 今日 AI 語義聚類摘要\n"
        def clean_label(l):
            if not isinstance(l, str): return None
            l = re.sub(r'\(.*?\)', '', l)
            l = re.sub(r'（.*?）', '', l)
            return l.strip() if l else None

        clean_clusters = df['cluster_label'].apply(clean_label).dropna()
        if not clean_clusters.empty:
            cluster_counts = clean_clusters.value_counts().head(10)
            report += "| 聚類主題 | 頻次 | 佔比 |\n"
            report += "| :--- | :--- | :--- |\n"
            for label, count in cluster_counts.items():
                pct = (count / len(clean_clusters)) * 100
                report += f"| {label} | {count} | {pct:.1f}% |\n"
            report += "\n"

    report += "## 七、 今日典型負面反饋\n"
    if not neg_reviews:
        report += "今日無顯著負面反饋。\n\n"
    else:
        for i, content in enumerate(neg_reviews):
            display_content = (content[:200] + '...') if len(content) > 200 else content
            report += f"{i+1}. {display_content}\n\n"

    # Save today's report
    output_path = os.path.join(BASE_DIR, 'reports', f"daily_report_{TODAY}.md")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"Daily report generated: {output_path}")

if __name__ == "__main__":
    generate_today_report()
