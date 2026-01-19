
import sqlite3
import pandas as pd
import json
import collections
import jieba
import os
import re

# Project root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Database path
DB_PATH = os.path.join(BASE_DIR, 'data', 'jump_reviews.db')
# Configuration: Default to the first day of the current month
import datetime
START_DATE = datetime.datetime.now().replace(day=1).strftime('%Y-%m-%d')
END_DATE = None  # Set to None for "until now"

def load_stopwords():
    stop_path = os.path.join(BASE_DIR, 'config', 'stopwords.txt')
    if os.path.exists(stop_path):
        with open(stop_path, 'r', encoding='utf-8') as f:
            return set([line.strip() for line in f if line.strip()])
    return set()

def generate_report():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    date_filter = f"review_date >= '{START_DATE}'"
    if END_DATE:
        date_filter += f" AND review_date <= '{END_DATE}'"
    
    query = f"SELECT * FROM reviews WHERE {date_filter}"
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print(f"No data found after {START_DATE}")
        return

    # Ensure date is datetime object
    df['review_date'] = pd.to_datetime(df['review_date'])

    total_reviews = len(df)
    avg_sentiment = df['sentiment_score'].mean()
    sentiment_counts = df['sentiment_label'].value_counts().to_dict()

    # Aspect analysis aggregation
    aspect_feedback = {}
    hero_feedback = {}

    for _, row in df.iterrows():
        if pd.isna(row['detailed_analysis']):
            continue
        try:
            analysis = json.loads(row['detailed_analysis'])
            
            # System Aspects
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

            # Hero Aspects
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
        except:
            continue

    # Word Frequency
    stopwords = load_stopwords()
    all_words = []
    for txt in df['content'].dropna():
        words = [w for w in jieba.cut(str(txt)) if len(w) > 1 and w not in stopwords and not re.match(r'^[0-9.]+$', w)]
        all_words.extend(words)
    word_freq = collections.Counter(all_words).most_common(20)

    # Top Complaints (Sample of negative reviews)
    neg_reviews = df[df['sentiment_label'] == 'Negative'].sort_values(by='sentiment_score').head(10)['content'].tolist()

    # Source breakdown
    source_counts = df['source'].value_counts().to_dict()

    # Format the report
    start_date_str = START_DATE
    end_date_str = df['review_date'].max().strftime('%Y-%m-%d') if 'review_date' in df.columns else '未知'
    
    report = f"# 《漫画群星：大集结》舆情监测报告 ({start_date_str} 至 {end_date_str})\n\n"
    report += f"**报告生成日期**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n"
    report += f"**数据范围**: {start_date_str} 至 {end_date_str}\n\n"

    report += "## 一、 舆情概况\n"
    report += f"- **总采集评论数**: {total_reviews} 条\n"
    report += f"- **整体情感平均分**: {avg_sentiment:.2f} (0=极差, 1=极好)\n"
    report += f"- **情感分布**:\n"
    for label, count in sentiment_counts.items():
        percentage = (count / total_reviews) * 100
        report += f"  - {label}: {count} ({percentage:.1f}%)\n"
    report += "\n"

    report += "## 二、 渠道分布\n"
    for source, count in source_counts.items():
        report += f"- **{source}**: {count} 条\n"
    report += "\n"

    report += "## 三、 核心话题分布 (System Aspects)\n"
    report += "| 话题维度 | 总提及次数 | 正面 | 负面 | 正向率 |\n"
    report += "| :--- | :--- | :--- | :--- | :--- |\n"
    for aspect, stats in sorted(aspect_feedback.items(), key=lambda x: x[1]['total'], reverse=True):
        pos_rate = (stats['pos'] / stats['total'] * 100) if stats['total'] > 0 else 0
        report += f"| {aspect} | {stats['total']} | {stats['pos']} | {stats['neg']} | {pos_rate:.1f}% |\n"
    report += "\n"

    report += "## 四、 热点英雄反馈 (Heroes)\n"
    report += "| 英雄代号 | 总提及次数 | 正面 | 负面 | 正向率 |\n"
    report += "| :--- | :--- | :--- | :--- | :--- |\n"
    for hero, stats in sorted(hero_feedback.items(), key=lambda x: x[1]['total'], reverse=True)[:15]:
        pos_rate = (stats['pos'] / stats['total'] * 100) if stats['total'] > 0 else 0
        report += f"| {hero} | {stats['total']} | {stats['pos']} | {stats['neg']} | {pos_rate:.1f}% |\n"
    report += "\n"

    report += "## 五、 关注焦点 (关键词 Top 20)\n"
    report += ", ".join([f"{word}({count})" for word, count in word_freq])
    report += "\n\n"

    # Semantic Clustering Analysis
    if 'cluster_label' in df.columns:
        report += "## 六、 AI 语义聚类分析 (Semantic Clustering)\n"
        # Clean labels
        def clean_label(l):
            if not isinstance(l, str): return None
            l = re.sub(r'\(.*?\)', '', l)
            l = re.sub(r'（.*?）', '', l)
            l = l.replace('****', '').strip()
            return l if l else None

        clean_clusters = df['cluster_label'].apply(clean_label).dropna()
        if not clean_clusters.empty:
            cluster_counts = clean_clusters.value_counts().head(15)
            
            report += "| 核心话题 | 提及频次 | 占比 |\n"
            report += "| :--- | :--- | :--- |\n"
            for label, count in cluster_counts.items():
                pct = (count / len(clean_clusters)) * 100
                report += f"| {label} | {count} | {pct:.1f}% |\n"
            report += "\n"
        else:
            report += "暂无聚类数据，请运行语义聚类脚本。\n\n"


    report += "## 七、 典型负面反馈摘选\n"
    for i, content in enumerate(neg_reviews):
        # Truncate content if too long
        display_content = (content[:200] + '...') if len(content) > 200 else content
        report += f"{i+1}. {display_content}\n\n"

    report += "## 八、 总结与建议\n"
    
    # Simple logic-based summary
    if avg_sentiment < 0.4:
        report += "- **综述**: 近期舆情呈现高度负面，玩家不满情绪显著。\n"
    elif avg_sentiment < 0.6:
        report += "- **综述**: 舆情相对平稳，但仍存在不少负面反馈，需重点优化核心痛点。\n"
    else:
        report += "- **综述**: 舆情整体正向，玩家对近期内容认可度较高。\n"
    
    if aspect_feedback.get('Welfare', {}).get('neg', 0) > aspect_feedback.get('Welfare', {}).get('pos', 0):
        report += "- **付费/福利**: 玩家对价格或福利活动存在较多抱怨，建议审阅近期商业化策略。\n"
    if aspect_feedback.get('Optimization', {}).get('neg', 0) > 5:
        report += "- **性能优化**: 仍有玩家反馈卡顿、掉帧问题，建议持续优化客户端性能。\n"
    if aspect_feedback.get('Network', {}).get('neg', 0) > 5:
        report += "- **网络体验**: 网络延迟(460)问题是部分玩家的痛点。\n"

    # Save report to a file in reports directory
    reports_dir = os.path.join(BASE_DIR, 'reports')
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
        
    # Generate filename based on date range or month
    month_suffix = pd.to_datetime(START_DATE).strftime('%Y%m')
    output_path = os.path.join(reports_dir, f"public_opinion_report_{month_suffix}.md")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"Report generated at: {output_path}")
    print("--- REPORT PREVIEW ---")
    print(report[:1000] + "...")

if __name__ == "__main__":
    generate_report()
