import streamlit as st
import os
import sys
import html

# Add project root to path for Streamlit Cloud
# Use insert(0) to ensure this path takes precedence
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import time
import io
import itertools
from collections import Counter

from core.db import get_all_data, get_all_chats, init_db
# These were unused in the UI and causing ImportErrors due to missing/moved functions
# from core.analysis import analyze_sentiment, detailed_aspect_analysis

from config.settings import GAMES
import jieba
import re
import sqlite3

# --- Segmentation Optimization ---
@st.cache_resource
def init_segmentation():
    """Add hero names and sentiment keywords to jieba for better segmentation."""
    # 1. From GAMES keywords
    for game in GAMES.values():
        if 'keywords' in game:
            for word in game['keywords'].keys():
                if len(word) > 1:
                    jieba.add_word(word)
    
    # 2. Strong sentiment keywords for better identification
    strong_keywords = ["贵得要死", "吃相难看", "割韭菜", "白嫖", "送福袋", "还原度", "匹配机制", "连败", "连胜"]
    for kw in strong_keywords:
        jieba.add_word(kw)
    
    return True

init_segmentation()

# --- Advanced Tokenization Setup ---
try:
    import nltk
    from nltk.stem import WordNetLemmatizer
    from pythainlp import word_tokenize as thai_tokenize
    # Download necessary NLTK data
    nltk.download('wordnet', quiet=True)
    nltk.download('omw-1.4', quiet=True)
    lemmatizer = WordNetLemmatizer()
    HAS_SPECIALIZED = True
except ImportError:
    HAS_SPECIALIZED = False

def smart_tokenize(text, source=None, stopwords=None):
    """
    Advanced multi-language tokenization:
    - Thai: pythainlp (Dictionary-based)
    - English: NLTK Lemmatization + Regex
    - Chinese: Jieba
    """
    if not text or not isinstance(text, str):
        return []
    
    text = text.lower()
    
    # 1. Detect Thai Content (Thai characters: \u0E00-\u0E7F)
    if re.search(r'[\u0E00-\u0E7F]', text):
        if HAS_SPECIALIZED:
            words = thai_tokenize(text, engine="newmm")
        else:
            words = re.findall(r'[\u0E00-\u0E7F]+', text)
            
    # 2. Detect Chinese Content (Simplified & Traditional)
    # Using a broader range \u4e00-\u9fff and source hints
    elif re.search(r'[\u4e00-\u9fff]', text) or (source and source.lower() in ['youtube', 'bahamut', 'discord']):
        words = list(jieba.cut(text))
        
    # 3. Primarily International / English
    else:
        # Regex for words
        raw_words = re.findall(r'\b[a-z]{2,}\b', text)
        if HAS_SPECIALIZED:
            # Lemmatize English words
            words = [lemmatizer.lemmatize(w) for w in raw_words]
        else:
            words = raw_words

    # 4. Global Filtering
    if stopwords:
        # Keep single characters if they are Chinese (very important for sentiment like '贵', '卡', '坑')
        return [w.strip() for w in words if (len(w.strip()) > 1 or re.search(r'[\u4e00-\u9fa5]', w)) and w.strip() not in stopwords and not re.match(r'^[0-9.]+$', w)]
    return [w.strip() for w in words if (len(w.strip()) > 1 or re.search(r'[\u4e00-\u9fa5]', w)) and not re.match(r'^[0-9.]+$', w)]


def load_stopwords():
    stop_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'stopwords.txt')
    if os.path.exists(stop_path):
        with open(stop_path, 'r', encoding='utf-8') as f:
            return set([line.strip() for line in f if line.strip()])
    return set()

def format_tooltip(meta):
    if not meta:
        return ""
    full_c = meta.get('full_content', '')
    # Remove extra spaces/newlines to keep it compact
    clean_c = " ".join(full_c.split())
    # Truncate to 100 characters as requested
    if len(clean_c) > 100:
        clean_c = clean_c[:100] + "..."
    
    # Safe quotes for HTML attributes
    clean_c = clean_c.replace("'", '’').replace('"', '”')
    source = meta.get('source', '未知')
    date = meta.get('date', '未知')
    
    return html.escape(f"完整评论: {clean_c}\n来源: {source}\n时间: {date}")

def load_events():
    events_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'events.json')
    if os.path.exists(events_path):
        try:
            with open(events_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return []

def add_events_to_fig(fig, events, start_date, end_date):
    if not events: return fig
    # Normalize filter dates
    s_dt = pd.to_datetime(start_date)
    e_dt = pd.to_datetime(end_date)
    
    for ev in events:
        try:
            ev_start = pd.to_datetime(ev['start'])
            ev_end = pd.to_datetime(ev['end'])
            
            # Show if event overlaps with filter
            if (ev_start <= e_dt) and (ev_end >= s_dt):
                fig.add_vrect(
                    x0=max(ev_start, s_dt), 
                    x1=min(ev_end, e_dt),
                    fillcolor=ev.get('color', 'rgba(150, 150, 150, 0.15)'),
                    layer="below", line_width=0,
                    annotation_text=ev['name'],
                    annotation_position="top left",
                    annotation=dict(font_size=10, font_color="#666", bgcolor="white", opacity=0.8)
                )
        except: continue
    return fig

# Page Configuration
st.set_page_config(
    page_title="Multi-Game Monitor",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Authentication
def check_password():
    """Returns `True` if the user is authorized."""
    
    # 1. Check for public/local mode (no secrets)
    if "DB_USERNAME" not in st.secrets:
        return True

    # 2. Check if already authenticated via Session State
    if st.session_state.get("password_correct", False):
        return True
    
    # 3. Show Login Form
    st.header("Login")
    with st.form("auth_form"):
        # Use new keys to avoid conflicts with old session state
        input_user = st.text_input("Username", key="auth_username")
        input_pass = st.text_input("Password", type="password", key="auth_password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        # Check credentials
        is_valid = False
        
        # 1. Check legacy (DB_USERNAME)
        if (
            "DB_USERNAME" in st.secrets 
            and input_user == st.secrets["DB_USERNAME"]
            and input_pass == st.secrets["DB_TOKEN"]
        ):
            is_valid = True
            
        # 2. Check multiple users ([passwords] section)
        elif "passwords" in st.secrets:
            # secrets["passwords"] returns a AttrDict/Dict
            if input_user in st.secrets["passwords"] and input_pass == st.secrets["passwords"][input_user]:
                is_valid = True
                
        if is_valid:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("😕 User not known or password incorrect")
            
    return False

if not check_password():
    st.info("Please log in to continue.")
    st.stop()

# --- Helper Functions (New Style) ---
def render_hero(title, subtitle="Sentiment Analysis System"):
    st.markdown(f"""
        <div class="hero-box">
            <h1 style="margin: 0; font-size: 2.4em; letter-spacing: 0.05em; font-family: 'Noto Serif JP', serif;">{title}</h1>
            <div style="height: 2px; background: #9F353A; width: 60px; margin: 20px 0;"></div>
            <p style="color: #666; font-size: 1em; text-transform: uppercase; letter-spacing: 0.15em; font-weight: 500;">{subtitle}</p>
        </div>
    """, unsafe_allow_html=True)

# Traditional Japanese Color Palette
JP_COLORS = ["#165E83", "#9F353A", "#D0AF4C", "#1B4D3E", "#70649A", "#B14B28"]

# Custom CSS
# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@700&family=Noto+Sans+SC:wght@400;500;700&family=Inter:wght@400;600&display=swap');
    
    :root {
        --header-font: 'Noto Serif JP', 'Noto Sans SC', serif;
        --body-font: 'Inter', 'Noto Sans SC', sans-serif;
        --accent-color: #9F353A;
    }

    .main {
        background-color: #F9F7F2;
        color: #2D2D2D;
        font-family: var(--body-font);
    }
    
    /* Standardized Header Styles */
    h1 {
        font-family: var(--header-font) !important;
        font-size: 2.2rem !important;
        color: #1A1A1A !important;
        font-weight: 700 !important;
        margin-bottom: 0.5rem !important;
        letter-spacing: -0.02em !important;
    }
    
    h2 {
        font-family: var(--header-font) !important;
        font-size: 1.6rem !important;
        color: #333 !important;
        border-bottom: 2px solid #E0DED7;
        padding-bottom: 8px;
        margin-top: 2rem !important;
        margin-bottom: 1.2rem !important;
    }
    
    h3 {
        font-family: var(--header-font) !important;
        font-size: 1.25rem !important;
        color: var(--accent-color) !important;
        margin-top: 1.5rem !important;
        margin-bottom: 0.8rem !important;
    }

    .stMetric label {
        font-family: var(--body-font) !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #666;
    }
    
    .stMetric [data-testid="stMetricValue"] {
        font-family: var(--header-font) !important;
        font-size: 1.8rem !important;
    }

    .hero-box {
        background: #FFFFFF;
        padding: 30px;
        border-left: 6px solid var(--accent-color);
        margin-bottom: 40px;
        border-radius: 4px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }

    /* Chart improvement - no border */
    .plot-container {
        border: none;
        background: transparent;
        padding: 0;
    }

    /* Feedback Box Styles */
    .feedback-box {
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 10px;
        font-size: 0.92rem;
        line-height: 1.6;
        border: 1px solid #EAE6DF;
        transition: all 0.2s ease;
        background: #FFFFFF;
        box-shadow: 0 2px 4px rgba(0,0,0,0.03);
    }
    .feedback-box:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transform: translateY(-1px);
    }
    .feedback-pos {
        border-left: 5px solid #2ecc71;
    }
    .feedback-neg {
        border-left: 5px solid #e74c3c;
    }
    .mode-tag {
        display: inline-block;
        padding: 2px 8px;
        background: #f0f0f0;
        border-radius: 4px;
        font-size: 0.75rem;
        color: #555;
        margin-right: 8px;
        font-weight: 600;
        vertical-align: middle;
        border: 1px solid #ddd;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=60)
def load_data(game_filter=None):
    init_db()
    df = get_all_data()
    if not df.empty:
        if 'review_date' in df.columns:
            df['review_date'] = df['review_date'].apply(lambda x: pd.to_datetime(str(x), errors='coerce') if pd.notnull(x) else pd.NaT)
        if 'sentiment_score' in df.columns:
            df['sentiment_score'] = pd.to_numeric(df['sentiment_score'], errors='coerce')
        
        # Filter by game
        if game_filter:
            # Handle legacy data with no game_id as jump_assemble
            if 'game_id' not in df.columns:
                 df['game_id'] = 'jump_assemble'
            else:
                 df['game_id'] = df['game_id'].fillna('jump_assemble')
                 
            df = df[df['game_id'] == game_filter]
            
    return df



# Sidebar
with st.sidebar:
    st.title("舆情监控中心")
    
    # Game Selector
    game_keys = list(GAMES.keys())
    game_names = [GAMES[k]['name'] for k in game_keys]
    selected_game_name = st.selectbox("选择项目", game_names)
    selected_game_key = game_keys[game_names.index(selected_game_name)]
    
    st.caption(f"当前项目: {selected_game_name}")
    st.markdown("---")
    
    # Navigation (Top Priority)
    menu = st.radio("导航", ["📊 总览大屏", "🧭 评论搜索", "📚 漫画专项", "🦸 英雄专项", "⚙️ 玩法反馈", "📄 分析月报", "🔧 配置管理"], index=0)
    st.markdown("---")
    
    # Load Data for Sidebar Filters
    df = load_data(selected_game_key)
    
    # Date Filter
    st.subheader("📅 时间筛选")
    today = pd.Timestamp.now().date()
    # Default to last 6 months
    start_date = st.date_input("开始日期", today - pd.Timedelta(days=180))
    end_date = st.date_input("结束日期", today)
    
    # Source Filter
    st.subheader("🌐 来源筛选")
    all_sources = sorted(list(df['source'].dropna().unique())) if 'source' in df.columns else []
    selected_sources = st.multiselect("选择来源", all_sources, default=all_sources)
    
    if "taptap_intl" in selected_sources:
        pass

    st.markdown("---")
    # Removed Download CSV/XLSX section as requested due to performance lag

# Filter by Source
if not df.empty and 'source' in df.columns and selected_sources:
    df = df[df['source'].isin(selected_sources)]

# Apply Date Filter
if not df.empty and 'review_date' in df.columns:
    # Convert inputs to datetime
    s_dt = pd.to_datetime(start_date)
    e_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1) # End of day
    
    mask = (df['review_date'] >= s_dt) & (df['review_date'] <= e_dt)
    df = df.loc[mask]


@st.cache_data(ttl=300)
def load_hero_ip_map(game_key):
    """Load mapping of Hero Code -> IP Group Name and Display Name based on heroes.json"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'heroes.json')
    hero_ip_map = {} # HeroCode -> IPName
    ip_hero_list = {} # IPName -> [HeroCodes]
    hero_display_map = {} # HeroCode -> First Alias (Display Name)
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                fc = json.load(f)
                if game_key in fc and "Groups" in fc[game_key]:
                    groups = fc[game_key]["Groups"]
                    for g_name, g_content in groups.items():
                        # g_content is {HeroCode: [Aliases]}
                        codes = list(g_content.keys())
                        ip_hero_list[g_name] = codes
                        for c, aliases in g_content.items():
                            hero_ip_map[c] = g_name
                            # The first alias is usually the primary Chinese name
                            hero_display_map[c] = aliases[0] if aliases else c
                            
        except Exception as e:
            print(f"Error loading hero map: {e}")
            
    return hero_ip_map, ip_hero_list, hero_display_map

@st.cache_data(ttl=300)
def process_trends(df, hero_ip_map):
    """Process raw reviews into IP and Hero trend data."""
    if df.empty or 'detailed_analysis' not in df.columns:
        return pd.DataFrame(), pd.DataFrame()
        
    ip_records = []
    hero_records = []
    
    for _, row in df.iterrows():
        try:
            if pd.isna(row['detailed_analysis']): continue
            data = json.loads(row['detailed_analysis'])
            heroes = data.get("Heroes", {})
            
            review_date = row['review_date']
            sentiment = row['sentiment_score'] if 'sentiment_score' in row else 0.5
            
            # Track IPs mentioned in this review to avoid double counting IP heat per review (optional, but let's count all mentions)
            # Actually, if a review mentions Goku and Vegeta, it counts twice for Dragon Ball? Usually yes for "Heat".
            
            for h_code in heroes.keys():
                ip_group = hero_ip_map.get(h_code, "Unknown")
                
                # Hero Record
                hero_records.append({
                    "date": review_date,
                    "hero": h_code,
                    "ip": ip_group,
                    "sentiment": sentiment,
                    "count": 1
                })
                
                # IP Record
                if ip_group != "Unknown":
                    ip_records.append({
                        "date": review_date,
                        "ip": ip_group,
                        "sentiment": sentiment,
                        "count": 1
                    })
                    
        except:
            continue
            
    return pd.DataFrame(ip_records), pd.DataFrame(hero_records)


if menu == "📊 总览大屏":
    render_hero(f"{selected_game_name} Overview", "舆情总览")
    if df.empty:
        st.warning("暂无数据，请去爬虫控制台抓取。")
    else:
        # Top Metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("总评论数", len(df))
        c2.metric("平均情感", f"{df['sentiment_score'].mean():.2f}" if 'sentiment_score' in df.columns else "0")
        
        # Sentiment Chart
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("😊 情感倾向")
            if 'sentiment_label' in df.columns:
                counts = df['sentiment_label'].value_counts().reset_index()
                counts.columns = ['Label', 'Count']
                fig = px.pie(counts, values='Count', names='Label', color='Label',
                             title='玩家情感构成分布',
                             color_discrete_map={'Positive':'#2ecc71', 'Negative':'#e74c3c', 'Neutral':'#95a5a6'})
                fig.update_layout(
                    height=350,
                    font_family="Inter", 
                    title_font=dict(size=18, family="Noto Serif JP", color="#1A1A1A"),
                    margin=dict(t=60, b=20, l=40, r=40),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with c2:
            st.subheader("⭐ 评分分布")
            if 'rating' in df.columns:
                rc = df['rating'].value_counts().sort_index().reset_index()
                rc.columns = ['Star', 'Count']
                rc['Star'] = rc['Star'].replace({0: '期待/0星'})
                fig_star = px.bar(rc, x='Star', y='Count', 
                                 title='App Store / TapTap 评分分布',
                                 template="plotly_white")
                fig_star.update_traces(marker_color=JP_COLORS[0], marker_line_color='#bcaf9f', marker_line_width=1)
                fig_star.update_layout(
                    height=350,
                    font_family="Inter", 
                    title_font=dict(size=18, family="Noto Serif JP", color="#1A1A1A"),
                    margin=dict(t=60, b=20, l=40, r=40),
                    xaxis=dict(title=None, showgrid=False),
                    yaxis=dict(title=None, gridcolor="#EEE"),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_star, use_container_width=True)



        # 1.25 趋势关联分析 (Trend Analysis)
        st.markdown("---")
        st.subheader("📉 舆情波动与事件关联")
        
        events = load_events()
        if not df.empty:
            # Prepare Daily Stats
            daily_stats = df.groupby(df['review_date'].dt.date).agg({
                'id': 'count',
                'sentiment_score': 'mean'
            }).reset_index()
            daily_stats.columns = ['date', 'count', 'sentiment']
            
            # Sub-header for Event Info
            if events:
                evt_list = []
                for ev in events:
                    if (pd.to_datetime(ev['start']) <= pd.to_datetime(end_date)) and (pd.to_datetime(ev['end']) >= pd.to_datetime(start_date)):
                        evt_list.append(f"`{ev['name']}` ({ev['start']} ~ {ev['end']})")
                if evt_list:
                    st.caption(f"当前时段关联事件: {' | '.join(evt_list)}")

            # Draw Dual Axis Chart
            fig_trend = go.Figure()
            # Volume (Bar)
            fig_trend.add_trace(go.Bar(
                x=daily_stats['date'], y=daily_stats['count'], name='评论量',
                marker_color='rgba(200, 200, 200, 0.3)', yaxis='y'
            ))
            # Sentiment (Line)
            fig_trend.add_trace(go.Scatter(
                x=daily_stats['date'], y=daily_stats['sentiment'], name='平均情感',
                line=dict(color=JP_COLORS[1], width=3), yaxis='y2'
            ))
            
            # Add Events
            fig_trend = add_events_to_fig(fig_trend, events, start_date, end_date)
            
            fig_trend.update_layout(
                title="舆情趋势与关键事件关联分析",
                height=350,
                template='plotly_white',
                font_family="Inter", title_font_family="Noto Serif JP",
                hovermode='x unified',
                margin=dict(t=30, b=20),
                legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
                yaxis=dict(title='评论数', side='left', showgrid=False),
                yaxis2=dict(title='情感分', side='right', overlaying='y', range=[0, 1], showgrid=True, gridcolor="#f0f0f0"),
                xaxis=dict(title=None, showgrid=False)
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        # 1. Activity Heatmap (Standard GitHub Contribution Graph)
        st.markdown("---")
        st.subheader("🗓️ 评论活跃度")
        
        if not df.empty and 'review_date' in df.columns:
            import numpy as np
            
            # 1. Data Preparation
            h_df = df.copy()
            h_df['review_date'] = pd.to_datetime(h_df['review_date']).dt.normalize()
            
            # 2. Generate Full Range
            all_dates = pd.date_range(start=start_date, end=end_date)
            base_df = pd.DataFrame({'review_date': all_dates})
            base_df['day_of_week'] = base_df['review_date'].dt.dayofweek # 0=Mon, 6=Sun
            base_df['month_name'] = base_df['review_date'].dt.strftime('%b')
            base_df['date_str'] = base_df['review_date'].dt.strftime('%b %d, %Y')
            
            # 3. Align to Weeks (Monday-based columns)
            # Find the starting Monday for the entire grid
            start_of_grid = all_dates.min() - pd.Timedelta(days=all_dates.min().dayofweek)
            base_df['week_num'] = (base_df['review_date'] - start_of_grid).dt.days // 7
            
            # 4. Aggregate Actual Data
            agg = h_df.groupby('review_date').size().reset_index(name='count')
            merged = pd.merge(base_df, agg, on='review_date', how='left').fillna(0)
            
            # 5. Pivot for Layout
            # Rows: Weekday (0-6), Columns: Week Index
            pivot_z = merged.pivot(index='day_of_week', columns='week_num', values='count').fillna(0)
            pivot_date = merged.pivot(index='day_of_week', columns='week_num', values='date_str')
            
            unique_weeks = sorted(merged['week_num'].unique())
            
            # 6. Prepare X-axis Month Labels
            x_labels = []
            last_m = ""
            for wn in unique_weeks:
                # Get the month of the first day of this week
                m = merged[merged['week_num'] == wn]['month_name'].iloc[0]
                if m != last_m:
                    x_labels.append(m)
                    last_m = m
                else:
                    x_labels.append("")

            # 7. Custom Hover Text
            custom_hover = []
            for r in range(7):
                row_hover = []
                for c in range(len(unique_weeks)):
                    d_str = pivot_date.iloc[r, c] if c < pivot_date.shape[1] else ""
                    cnt = int(pivot_z.iloc[r, c]) if c < pivot_z.shape[1] else 0
                    if d_str:
                        row_hover.append(f"{d_str}<br>{cnt} reviews")
                    else:
                        row_hover.append("")
                custom_hover.append(row_hover)

            # 8. Render using go.Heatmap for precise control
            colorscale = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"] # GitHub Greens
            
            fig = go.Figure(data=go.Heatmap(
                z=pivot_z.values,
                x=list(range(len(unique_weeks))),
                y=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                colorscale=colorscale,
                showscale=False,
                xgap=3,
                ygap=3,
                hoverinfo="text",
                text=custom_hover
            ))
            
            fig.update_layout(
                height=220,
                margin=dict(t=40, b=20, l=40, r=20),
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(
                    tickmode='array',
                    tickvals=list(range(len(unique_weeks))),
                    ticktext=x_labels,
                    side='top',
                    showgrid=False,
                    zeroline=False,
                    fixedrange=True
                ),
                yaxis=dict(
                    autorange="reversed",
                    tickmode='array',
                    tickvals=[1, 3, 5],
                    ticktext=["Mon", "Wed", "Fri"],
                    showgrid=False,
                    zeroline=False,
                    fixedrange=True
                )
            )
            # Ensure square cells
            fig.update_yaxes(scaleanchor="x", scaleratio=1)
            
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        # 1.5 热点演进路线 (Topic Evolution)
        st.markdown("---")
        st.subheader("📈 核心话题演进趋势")
        
        if not df.empty and 'detailed_analysis' in df.columns:
            # 准备数据：提取日期和系统维度
            topic_trend_data = []
            for _, row in df.iterrows():
                if pd.isna(row['detailed_analysis']): continue
                try:
                    analysis = json.loads(row['detailed_analysis'])
                    # Aggregate by day
                    date = pd.to_datetime(row['review_date']).normalize()
                    
                    # 统计系统维度 (Optimization, Network, Matchmaking, Welfare)
                    system_aspects = analysis.get("System", {})
                    for aspect, items in system_aspects.items():
                        if items: # 该评论提到了这个维度
                            topic_trend_data.append({"date": date, "topic": aspect, "count": 1})
                except:
                    continue
            
            if topic_trend_data:
                trend_df = pd.DataFrame(topic_trend_data)
                
                # Apply date filter
                s_dt_norm = pd.to_datetime(start_date).normalize()
                e_dt_norm = pd.to_datetime(end_date).normalize()
                trend_df = trend_df[(trend_df['date'] >= s_dt_norm) & (trend_df['date'] <= e_dt_norm)]
                
                if not trend_df.empty:
                    # Time Aggregation Selector
                    agg_col, _ = st.columns([1, 4])
                    with agg_col:
                        agg_type = st.radio("时间聚合", ["日", "周", "月"], index=1, horizontal=True)
                    
                    # Frequency Map
                    freq_map = {"日": "D", "周": "W-MON", "月": "M"} # Use 'M' for months in to_period
                    
                    # Aggregation Logic
                    bar_df = trend_df.copy()
                    bar_df['date'] = bar_df['date'].dt.to_period(freq_map[agg_type]).dt.to_timestamp()
                    bar_df = bar_df.groupby(['date', 'topic']).size().reset_index(name='mentions')
                    
                    # 绘制堆叠柱状图
                    fig_bar = px.bar(bar_df, x='date', y='mentions', color='topic',
                                    barmode='stack',
                                    template="plotly_white",
                                    color_discrete_sequence=JP_COLORS,
                                    labels={'date': '日期', 'mentions': '提及次数', 'topic': '关注维度'})
                    fig_bar.update_layout(
                        title="核心话题热度演进",
                        height=400,
                        font_family="Inter", title_font_family="Noto Serif JP",
                        margin=dict(t=10, b=0, l=0, r=0),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        xaxis=dict(title=None),
                        yaxis=dict(title="提及次数")
                    )
                    
                    # Add Events to Topic Evolution
                    fig_bar = add_events_to_fig(fig_bar, events, start_date, end_date)
                    
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    st.info("💡 选定时间范围内暂无话题提取数据。")
            else:
                st.info("💡 暂无话题提取数据。请确保已在爬虫管理中执行‘深度分析’。")

        # 1.6 关键词飙升榜 (Anomaly Detection)
        st.markdown("---")
        st.subheader("🚀 热词飙升榜")
        st.caption("对比过去 7 天与更早 21 天，挖掘讨论热度增长最快的关键词")

        if not df.empty and 'content' in df.columns:
            from collections import Counter
            
            # 1. Split data into Recent vs Baseline
            # Use the latest date in the filtered dataframe as the reference point
            latest_date = df['review_date'].max().normalize()
            recent_cutoff = latest_date - pd.Timedelta(days=7)
            baseline_cutoff = latest_date - pd.Timedelta(days=28)
            
            df_recent = df[df['review_date'] >= recent_cutoff]
            df_baseline = df[(df['review_date'] < recent_cutoff) & (df['review_date'] >= baseline_cutoff)]
            
            if len(df_recent) > 5 and len(df_baseline) > 5:
                stopwords = load_stopwords()
                
                def get_word_freq(dataframe):
                    all_words = []
                    for _, row in dataframe.iterrows():
                        txt = row['content']
                        src = row.get('source', '').lower()
                        # Use smart_tokenize with source context
                        words = smart_tokenize(txt, source=src, stopwords=stopwords)
                        all_words.extend(words)
                    counts = Counter(all_words)
                    total = sum(counts.values())
                    return counts, total

                counts_r, total_r = get_word_freq(df_recent)
                counts_b, total_b = get_word_freq(df_baseline)
                
                # 2. Calculate Growth Score
                # Score = (Recent_Freq + epsilon) / (Baseline_Freq + epsilon)
                rising_data = []
                for word, c_r in counts_r.items():
                    if c_r < 3: continue # Filter noise: word must appear at least 3 times recently
                    
                    freq_r = c_r / total_r
                    c_b = counts_b.get(word, 0)
                    freq_b = c_b / total_b if total_b > 0 else 0
                    
                    # Growth logic: Simple multiple of frequency
                    # Use a small floor for baseline freq to avoid division by zero and over-weighting brand new words
                    floor_freq = 0.5 / total_b if total_b > 0 else 0.0001
                    growth = freq_r / max(freq_b, floor_freq)
                    
                    rising_data.append({
                        "关键词": word, 
                        "最近提及": c_r, 
                        "基准提及": c_b, 
                        "增长倍率": round(growth, 1)
                    })
                
                if rising_data:
                    rising_df = pd.DataFrame(rising_data).sort_values("增长倍率", ascending=False).head(10)
                    
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        fig_rising = px.bar(rising_df, x="增长倍率", y="关键词", orientation='h', 
                                           color="增长倍率", color_continuous_scale="Reds",
                                           title="Top 10 飙升关键词",
                                           text="最近提及")
                        fig_rising.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False)
                        st.plotly_chart(fig_rising, use_container_width=True)
                    with c2:
                        st.write("📊 详情数据")
                        st.dataframe(rising_df[["关键词", "增长倍率", "最近提及"]], hide_index=True)
                else:
                    st.info("尚未发现明显的词频异动。")
            else:
                st.info("数据量不足（需要至少 7 天以上的历史数据进行对比）。")


elif menu == "🧭 评论搜索":
    render_hero("Comment Search", "AI 聚类与全量评论搜索")
    
    tab1, tab2 = st.tabs(["🗺️ 语义分布图", "🔍 全语境搜索"])
    
    with tab1:
        st.markdown("""
        💡 **如何阅读此图？**
        - 每一个点代表一条玩家评论。位置越接近的点，语义越相似。
        - 不同的颜色代表大模型自动识别出的 **“隐藏话题”**。
        - **悬停** 鼠标可预览具体评论内容。
        """)
        
        if df.empty or 'x' not in df.columns or df['x'].isnull().all():
            st.warning("📊 语义地图暂未生成。")
            st.info("请确保已在 `.env` 配置 `GEMINI_API_KEY` 并运行 `python scripts/process_semantic.py` 以进行向量化处理。")
        else:
            # Filter for data that has coordinates
            map_df = df.dropna(subset=['x', 'y', 'cluster_label'])
            
            if map_df.empty:
                st.info("尚未进行向量化分析，请运行后台脚本。")
            else:
                # 0. Pre-clean labels for display
                def clean_label_display(l):
                    if not isinstance(l, str): return l
                    l = re.sub(r'\(.*?\)', '', l) # Remove (Pinyin)
                    l = re.sub(r'（.*?）', '', l) # Remove (括号内容)
                    return l.replace('****', '').strip()
                
                map_df['cluster_label'] = map_df['cluster_label'].apply(clean_label_display)

                # 1. Map rendering (Full Width)
                fig_map = px.scatter(
                    map_df, x='x', y='y',
                    color='cluster_label',
                    hover_data={'content': True, 'x': False, 'y': False, 'cluster_label': False},
                    title="全量舆情语义分布图",
                    template="plotly_white",
                    color_discrete_sequence=px.colors.qualitative.Prism,
                    height=650
                )
                
                fig_map.update_traces(marker=dict(size=8, opacity=0.7, line=dict(width=1, color='White')))
                fig_map.update_layout(
                    font_family="Inter", 
                    title_font_family="Noto Serif JP",
                    showlegend=True,
                    legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02, title="话题分类"),
                    xaxis=dict(showgrid=False, showticklabels=False, title=""),
                    yaxis=dict(showgrid=False, showticklabels=False, title=""),
                    margin=dict(l=0, r=0, t=40, b=0)
                )
                st.plotly_chart(fig_map, use_container_width=True)
                
                # 2. Stats and search rendering (Below the map)
                st.markdown("---")
                st.subheader("📋 话题分布详情")
                cluster_stats = map_df.groupby('cluster_label').size().reset_index(name='count')
                cluster_stats = cluster_stats.sort_values('count', ascending=False)
                
                st.dataframe(
                    cluster_stats,
                    column_config={
                        "cluster_label": "核心话题名",
                        "count": st.column_config.NumberColumn("覆盖评论数", format="%d 💬")
                    },
                    hide_index=True,
                    use_container_width=True
                )

    with tab2:
        if not df.empty:
            search_col, sort_col = st.columns([3, 1])
            with search_col:
                search = st.text_input("输入关键词搜索（支持正则）", placeholder="例如: 延迟|卡顿")
                st.caption("💡 **搜索提示**：系统暂不支持简繁体自动转换。若需搜索港澳台/海外评论，请确保关键词与原文文字格式（简/繁）一致。")
            with sort_col:
                sort_order = st.selectbox("排序方式", ["时间倒序", "时间正序", "评分从低到高", "评分从高到低"])
            
            filtered_df = df
            if search:
                filtered_df = df[df['content'].str.contains(search, na=False, case=False, regex=True)]
            
            # Sort logic
            if sort_order == "时间倒序":
                filtered_df = filtered_df.sort_values('review_date', ascending=False)
            elif sort_order == "时间正序":
                filtered_df = filtered_df.sort_values('review_date', ascending=True)
            elif sort_order == "评分从低到高":
                filtered_df = filtered_df.sort_values('rating', ascending=True)
            elif sort_order == "评分从高到低":
                filtered_df = filtered_df.sort_values('rating', ascending=False)

            st.write(f"🔍 找到 {len(filtered_df)} 条匹配评论")
            st.markdown("---")
            
            # Pagination for search results to avoid lag
            items_per_page = 20
            num_pages = (len(filtered_df) // items_per_page) + 1 if len(filtered_df) > 0 else 1
            if num_pages > 1:
                page = st.number_input("页码", min_value=1, max_value=num_pages, step=1)
            else:
                page = 1
            
            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            
            for idx, row in filtered_df.iloc[start_idx:end_idx].iterrows():
                source_badge = row.get('source', 'Unknown')
                date_display = str(row.get('review_date', ''))
                
                try:
                    rating_val = float(row.get('rating', 0))
                except:
                    rating_val = 0
                rating_stars = "⭐" * int(rating_val) if pd.notna(rating_val) and rating_val > 0 else "无评分"
                
                s_score = row.get('sentiment_score', 0.5)
                try: s_score = float(s_score)
                except: s_score = 0.5
                s_score = s_score if pd.notna(s_score) else 0.5
                s_color = "#e74c3c" if s_score < 0.45 else ("#2ecc71" if s_score > 0.55 else "#95a5a6")
                
                label = row.get('sentiment_label', "Neutral")
                if pd.isna(label): label = "Neutral"
                
                c_title = row.get('content_title', '')
                c_url = row.get('content_url', '')
                title_html = f"<div style='margin-bottom: 5px;'><a href='{c_url}' target='_blank' style='color:#165E83;text-decoration:none;'>📺 <b>{c_title}</b></a></div>" if c_title else ""
                
                st.markdown(f"""
                    <div style="border-left: 4px solid {s_color}; padding: 10px; background: white; margin-bottom: 8px; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                        {title_html}
                        <div style="display: flex; justify-content: space-between; font-size: 0.8em; color: #666; margin-bottom: 5px;">
                            <span><b>{row.get('author','Unknown')}</b> ({source_badge}) {rating_stars}</span>
                            <span>{date_display} | Label: {label}</span>
                        </div>
                        <div style="font-size: 0.95em;">{row.get('content', '')}</div>
                    </div>
                """, unsafe_allow_html=True)

elif menu == "📚 漫画专项":
    render_hero("Manga Specialty", "IP 势力与角色热度分析")
    
    # Load Hero/IP Mapping
    hero_ip_map, ip_hero_list, hero_display_map = load_hero_ip_map(selected_game_key)
    
    # Process Data
    ip_df, hero_df = process_trends(df, hero_ip_map)
    
    if ip_df.empty:
        st.info("暂无 IP 相关分析数据。请先执行‘深度分析’以提取角色提及。")
    else:
        # Convert Hero Codes to Display Names
        hero_df['hero_name'] = hero_df['hero'].map(lambda x: hero_display_map.get(x, x))
        
        # ----------------------
        # 1. Manga IP Overview (Heat & Volume)
        # ----------------------
        st.subheader("🔥 IP 势力总览")
        
        # Aggregate by IP
        ip_stats = ip_df.groupby('ip').agg({
            'count': 'sum',
            'sentiment': 'mean'
        }).reset_index()
        
        # Filter out "Unknown" if necessary
        ip_stats = ip_stats[ip_stats['ip'] != 'Unknown']
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
             # Scatte Plot: Sentiment vs Volume
             fig_ip = px.scatter(ip_stats, x='sentiment', y='count',
                                size='count', color='ip',
                                text='ip',
                                labels={'sentiment': '平均情感 (0-1)', 'count': '评论提及量'},
                                title='IP 声量与情感分布',
                                color_discrete_sequence=JP_COLORS,
                                template="plotly_white")
             fig_ip.update_traces(textposition='top center')
             fig_ip.update_layout(
                 legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
             )
             st.plotly_chart(fig_ip, use_container_width=True)
             
        with col2:
             # Ranking Table
             st.write("🏆 热门 IP 排行")
             st.dataframe(
                 ip_stats.sort_values('count', ascending=False)[['ip', 'count', 'sentiment']],
                 column_config={
                     "sentiment": st.column_config.ProgressColumn("情感分", min_value=0, max_value=1, format="%.2f"),
                     "count": st.column_config.NumberColumn("热度")
                 },
                 hide_index=True,
                 use_container_width=True
             )
             
        st.markdown("---")
        
        # ----------------------
        # 2. Character Stacked Sentiment
        # ----------------------
        st.subheader("🎭 角色情感构成 (堆叠图)")
        
        # Filter Selector (Optional)
        f_col1, _ = st.columns([1, 1])
        all_ips = sorted(ip_stats['ip'].unique())
        with f_col1:
            selected_ips = st.multiselect("IP 筛选 (不选则默认全选)", all_ips, default=[])
        
        # Apply Filter
        plot_df = hero_df.copy()
        if selected_ips:
            plot_df = plot_df[plot_df['ip'].isin(selected_ips)]
        
        if not plot_df.empty:
            # Calculate Sentiment Buckets
            NEG_TH = 0.4
            POS_TH = 0.6
            
            hero_agg = plot_df.groupby('hero_name')['sentiment'].apply(list).reset_index()
            
            stacked_data = []
            for _, row in hero_agg.iterrows():
                scores = row['sentiment']
                pos = sum(1 for s in scores if s > POS_TH)
                neu = sum(1 for s in scores if NEG_TH <= s <= POS_TH)
                neg = sum(1 for s in scores if s < NEG_TH)
                total = len(scores)
                
                stacked_data.append({
                    "hero": row['hero_name'],
                    "Positive": pos,
                    "Neutral": neu,
                    "Negative": neg,
                    "Total": total
                })
            
            # Sort by Total Volume Descending
            stack_df = pd.DataFrame(stacked_data).sort_values('Total', ascending=False)
            
             # Limit to Top 50 if too many
            if len(stack_df) > 50:
                st.caption(f"数据显示 Top 50 热门角色 (共 {len(stack_df)} 个)")
                stack_df = stack_df.head(50)
            
            fig_stack = go.Figure()
            
            # Vertical Bars: X = Hero, Y = Count
            fig_stack.add_trace(go.Bar(
                x=stack_df['hero'], y=stack_df['Negative'], name='负面', 
                marker_color='#e74c3c'
            ))
            fig_stack.add_trace(go.Bar(
                x=stack_df['hero'], y=stack_df['Neutral'], name='中性', 
                marker_color='#95a5a6'
            ))
            fig_stack.add_trace(go.Bar(
                x=stack_df['hero'], y=stack_df['Positive'], name='正面', 
                marker_color='#2ecc71'
            ))
            
            fig_stack.update_layout(
                barmode='stack',
                title='角色热度与情感构成',
                xaxis_title='角色',
                yaxis_title='提及次数',
                template='plotly_white',
                height=500,
                xaxis_tickangle=-45,
                legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
            )
            st.plotly_chart(fig_stack, use_container_width=True)
            
            with st.expander("查看详细数据表"):
                st.dataframe(
                    stack_df,
                    column_config={
                        "hero": "角色名称",
                        "Total": st.column_config.NumberColumn("提及总数"),
                        "Positive": st.column_config.NumberColumn("正面反馈"),
                        "Neutral": st.column_config.NumberColumn("中性反馈"),
                        "Negative": st.column_config.NumberColumn("负面反馈")
                    },
                    use_container_width=True
                )
            
        else:
            st.info(f"当前筛选条件下暂无角色数据")

elif menu == "🦸 英雄专项":

    render_hero("Hero Feedback", "英雄专项反馈")
    
    if df.empty or 'detailed_analysis' not in df.columns:
        st.info("暂无详细分析数据")
    else:
        # Aggregate Hero Data
        hero_data = {} # {HeroName: {Dim: [items]}}
        
        for json_str in df['detailed_analysis'].dropna():
            try:
                data = json.loads(json_str)
                heroes = data.get("Heroes", {})
                for h_name, dims in heroes.items():
                    if h_name not in hero_data: hero_data[h_name] = {}
                    for dim, items in dims.items():
                        if dim not in hero_data[h_name]: hero_data[h_name][dim] = []
                        hero_data[h_name][dim].extend(items)
            except:
                pass
        
        if not hero_data:
            st.warning("暂无特定英雄的反馈数据。")
        else:
            # Load Groups from heroes.json for filtering
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'heroes.json')
            hero_groups = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        fc = json.load(f)
                        if selected_game_key in fc and "Groups" in fc[selected_game_key]:
                             raw_groups = fc[selected_game_key]["Groups"]
                             # Convert new Dict structure to List for UI filtering
                             # {GroupName: {Hero: [Aliases]}} -> {GroupName: [Hero]}
                             for g_name, g_heroes in raw_groups.items():
                                 if isinstance(g_heroes, dict):
                                     hero_groups[g_name] = list(g_heroes.keys())
                                 elif isinstance(g_heroes, list):
                                     hero_groups[g_name] = g_heroes
                                     
                             pass
                except: pass

            # Create a display map: CodeName -> Display Name
            display_map = {}
            hero_to_first_alias = {}
            
            # Load first aliases from heroes.json for best display names
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        fc = json.load(f)
                        if selected_game_key in fc and "Groups" in fc[selected_game_key]:
                             groups = fc[selected_game_key]["Groups"]
                             for g_heroes in groups.values():
                                 if isinstance(g_heroes, dict):
                                     for h_code, aliases in g_heroes.items():
                                         if aliases:
                                             hero_to_first_alias[h_code] = aliases[0]
                except: pass

            for h_code in hero_data.keys():
                # Priority 1: First alias from heroes.json (usually Simplified Chinese Full Name)
                if h_code in hero_to_first_alias:
                    display_map[h_code] = hero_to_first_alias[h_code]
                else:
                    # Fallback login: find shortest Chinese alias from keywords
                    keywords = GAMES[selected_game_key].get('keywords', {})
                    aliases = [k for k, v in keywords.items() if v == h_code]
                    chinese_aliases = [a for a in aliases if not re.search('[a-zA-Z]', a)]
                    if chinese_aliases:
                        display_map[h_code] = sorted(chinese_aliases, key=len)[0]
                    elif aliases:
                        display_map[h_code] = aliases[0]
                    else:
                        display_map[h_code] = h_code
            
            # Group Selection
            # 2026-01-07: Filter out heroes that are NOT in a configured group (remove unwanted IPs from UI)
            all_configured_heroes = set()
            if hero_groups:
                for h_list in hero_groups.values():
                    all_configured_heroes.update(h_list)
            
            selected_group_heroes = [h for h in hero_data.keys() if h in all_configured_heroes]

            if hero_groups:
                # Groups are sorted keys now
                group_names = ["全部"] + sorted(list(hero_groups.keys()))
                
                # Side-by-side selector layout
                f_c1, f_c2 = st.columns(2)
                
                with f_c1:
                    selected_group = st.selectbox("选择IP系列 (Anime Source)", group_names)
                
                # Filter Logic
                if selected_group != "全部":
                    # Filter heroes belonging to this group
                    allowed_heroes = set(hero_groups[selected_group])
                    selected_group_heroes = [h for h in hero_data.keys() if h in allowed_heroes]
                else:
                    # '全部': re-select all configured
                    selected_group_heroes = [h for h in hero_data.keys() if h in all_configured_heroes]
            
            if not selected_group_heroes:
                st.warning("该系列暂无相关反馈数据的英雄。")
                selected_hero_code = None
            else:
                # Sort by Display Name
                sorted_heroes = sorted(selected_group_heroes, key=lambda x: display_map.get(x, x))
                
                with f_c2:
                    selected_hero_code = st.selectbox("选择角色", sorted_heroes, format_func=lambda x: display_map.get(x, x))
                
                if selected_hero_code:
                    st.subheader(f"⚔️ {display_map.get(selected_hero_code, selected_hero_code)}")
                    
                    # --- Hero Trend Chart ---
                    # 1. Load Data for Trends
                    hero_ip_map, _, _ = load_hero_ip_map(selected_game_key)
                    _, hero_trend_df = process_trends(df, hero_ip_map)
                    
                    if not hero_trend_df.empty:
                        # Aggregation Selector
                        agg_type_h = st.radio("趋势时间粒度", ["周 (Weekly)", "日 (Daily)", "月 (Monthly)"], key="hero_trend_agg", horizontal=True)
                        freq_map_h = {"周 (Weekly)": "W-MON", "日 (Daily)": "D", "月 (Monthly)": "M"}
                        freq_code_h = freq_map_h[agg_type_h]
                        
                        this_hero_df = hero_trend_df[hero_trend_df['hero'] == selected_hero_code]
                        
                        if not this_hero_df.empty:
                            # Group by Date-Freq
                            h_stats = this_hero_df.groupby([pd.Grouper(key='date', freq=freq_code_h)]).agg({
                                'count': 'count',
                                'sentiment': 'mean'
                            }).reset_index()
                            
                            # Treat 0 volume as missing for dashed connection
                            h_stats['count'] = h_stats['count'].replace(0, None)
                            
                            fig_h = go.Figure()
                            # Volume
                            fig_h.add_trace(go.Scatter(
                                x=h_stats['date'], y=h_stats['count'], name='热度 (Mentions)',
                                line=dict(color=JP_COLORS[0], width=2, dash='dot'),
                                connectgaps=True,
                                mode='lines+markers'
                            ))
                            # Sentiment
                            fig_h.add_trace(go.Scatter(
                                x=h_stats['date'], y=h_stats['sentiment'], name='平均情感',
                                line=dict(color=JP_COLORS[1], width=3, dash='dot'),
                                connectgaps=True,
                                yaxis='y2',
                                mode='lines+markers'
                            ))
                            
                            layout_args = dict(
                                title=f"{display_map.get(selected_hero_code, selected_hero_code)} - 热度与情感走势",
                                xaxis=dict(
                                    title=None,
                                    tickformat="%Y-%m-%d", # Force date format to avoid 00:00:00.001
                                ),
                                yaxis=dict(title='热度', showgrid=False),
                                yaxis2=dict(title='情感', overlaying='y', side='right', range=[0, 1], showgrid=True),
                                legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
                                height=350,
                                template='plotly_white'
                            )

                            # Optimize display for single data point
                            if len(h_stats) == 1:
                                one_date = h_stats['date'].iloc[0]
                                layout_args['xaxis']['range'] = [
                                    one_date - pd.Timedelta(days=1),
                                    one_date + pd.Timedelta(days=1)
                                ]

                            fig_h.update_layout(**layout_args)
                            st.plotly_chart(fig_h, use_container_width=True)

                    dims = hero_data[selected_hero_code]
                    
                    tabs = st.tabs(["💭 综合", "🗡️ 技能", "🎨 形象", "💪 强度", "🔗 关联词网"])
                    
                    def render_feedback(dimension_key, tab_container):
                        with tab_container:
                            items = dims.get(dimension_key, [])
                            if not items:
                                st.caption("暂无相关反馈")
                                return
                            
                            # Deduplicate display
                            seen = set()
                            unique_items = []
                            for item in items:
                                txt_norm = item['text'].strip()
                                if txt_norm not in seen:
                                    seen.add(txt_norm)
                                    unique_items.append(item)
                            
                            pos = [i for i in unique_items if i['label'] == 'Positive']
                            neg = [i for i in unique_items if i['label'] == 'Negative']
                            
                            c1, c2 = st.columns(2)
                            with c1:
                                st.write(f"🙂 好评 ({len(pos)})")
                                for p in pos:
                                    meta = p.get('metadata')
                                    tooltip = format_tooltip(meta)
                                    st.markdown(f'<div class="feedback-box feedback-pos" title="{tooltip}">{html.escape(p["text"])}</div>', unsafe_allow_html=True)
                            with c2:
                                st.write(f"😡 差评/建议 ({len(neg)})")
                                for n in neg:
                                    meta = n.get('metadata')
                                    tooltip = format_tooltip(meta)
                                    st.markdown(f'<div class="feedback-box feedback-neg" title="{tooltip}">{html.escape(n["text"])}</div>', unsafe_allow_html=True)

                    
                    render_feedback("General", tabs[0])
                    render_feedback("Skill", tabs[1])
                    render_feedback("Visual", tabs[2])
                    render_feedback("Strength", tabs[3])

                    # --- New Tab: Keyword Co-occurrence Network ---
                    with tabs[4]:
                        st.subheader("🔗 核心关联词网络")
                        st.caption("分析玩家在讨论该英雄时，最常联想到的词汇组合。")
                        
                        # Collect all related texts
                        hero_texts = []
                        for dim_key in dims:
                            for item in dims[dim_key]:
                                hero_texts.append(item['text'])
                        
                        if len(hero_texts) < 3:
                            st.info("数据量较少，无法生成关联网络。")
                        else:
                            stopwords = load_stopwords()
                            # 1. Tokenize and clean
                            tokenized_docs = []
                            for idx, row in enumerate(hero_texts):
                                # Since hero_texts is a list, we might not have 'source' easily here
                                # But we can pass the source if we change how hero_texts is collected
                                words = smart_tokenize(row, stopwords=stopwords)
                                if words: tokenized_docs.append(list(set(words))) # Unique words per sentence
                            
                            # 2. Count Co-occurrences
                            pair_counts = Counter()
                            word_freq = Counter()
                            for doc in tokenized_docs:
                                for word in doc: word_freq[word] += 1
                                if len(doc) >= 2:
                                    for pair in itertools.combinations(sorted(doc), 2):
                                        pair_counts[pair] += 1
                            
                            if not pair_counts:
                                st.info("未发现显著的词汇关联。")
                            else:
                                # 3. Prepare Graph Data (Top 30 edges)
                                top_pairs = pair_counts.most_common(30)
                                nodes = set()
                                for p, c in top_pairs:
                                    nodes.add(p[0])
                                    nodes.add(p[1])
                                
                                # 4. Simple Circular Layout (Manual calculation for performance)
                                import math
                                node_list = list(nodes)
                                pos = {node: (math.cos(2*math.pi*i/len(node_list)), math.sin(2*math.pi*i/len(node_list))) for i, node in enumerate(node_list)}
                                
                                # 5. Draw Edges
                                edge_x, edge_y = [], []
                                for (u, v), w in top_pairs:
                                    edge_x.extend([pos[u][0], pos[v][0], None])
                                    edge_y.extend([pos[u][1], pos[v][1], None])
                                
                                edge_trace = go.Scatter(x=edge_x, y=edge_y, line=dict(width=1, color='#ddd'), hoverinfo='none', mode='lines')
                                
                                # 6. Draw Nodes
                                node_x, node_y, node_text, node_size = [], [], [], []
                                for node in node_list:
                                    node_x.append(pos[node][0])
                                    node_y.append(pos[node][1])
                                    node_text.append(f"{node} (提及:{word_freq[node]})")
                                    # Scale size based on frequency
                                    node_size.append(max(10, min(40, word_freq[node] * 3)))
                                
                                node_trace = go.Scatter(
                                    x=node_x, y=node_y, mode='markers+text',
                                    text=[n for n in node_list],
                                    textposition="top center",
                                    hoverinfo='text', hovertext=node_text,
                                    marker=dict(size=node_size, color='#9be9a8', line_width=2, line_color='#40c463')
                                )
                                
                                fig_net = go.Figure(data=[edge_trace, node_trace],
                                     layout=go.Layout(
                                        showlegend=False, hovermode='closest',
                                        margin=dict(b=0,l=0,r=0,t=40),
                                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                        height=500,
                                        plot_bgcolor='rgba(0,0,0,0)'
                                    ))
                                st.plotly_chart(fig_net, use_container_width=True)

elif menu == "⚙️ 玩法反馈":
    render_hero("Gameplay & System", "玩法与系统反馈")
    
    if df.empty or 'detailed_analysis' not in df.columns:
        st.info("暂无数据")
    else:
        sys_data = {}
        # Define keywords to filter out official posts
        official_filter_keywords = [
            "活动期间", "活动时间", "活动有效期", "贴吧专属福利", "截止至", 
            "获得**奖励用户名单", "严禁讨论", "吧友参与活动", 
            "加入玩家交流群", "宝贵反馈和建议", "盖楼送福利", "官方吧吧务组","衷心感谢大家",
            "礼包码激活方式","我们将基于本轮数据进行整理与优化","玩法规则"
        ]

        for json_str in df['detailed_analysis'].dropna():
            try:
                data = json.loads(json_str)
                system = data.get("System", {})
                for aspect, items in system.items():
                    if aspect not in sys_data: sys_data[aspect] = []
                    
                    # Filter items
                    filtered_items = []
                    for item in items:
                        text_content = item.get('text', '')
                        # Check if any official keyword is in the text
                        if not any(kw in text_content for kw in official_filter_keywords):
                            filtered_items.append(item)
                            
                    sys_data[aspect].extend(filtered_items)
            except:
                pass
            
        sorted_keys = sorted(sys_data.keys())
        emoji_map = {
            "Matchmaking": "⚖️ Matchmaking", 
            "Network": "📡 Network", 
            "Optimization": "🚀 Optimization", 
            "Welfare": "🎁 Welfare",
            "Gameplay": "🎮 Gameplay",
            "Visuals": "🎨 Visuals"
        }
        tab_labels = [emoji_map.get(k, k) for k in sorted_keys]

        tabs = st.tabs(tab_labels) if sys_data else []
        if not tabs:
            st.warning("暂无系统层面的反馈。")
        else:
            for i, aspect in enumerate(sorted_keys):
                with tabs[i]:
                    items = sys_data[aspect]
                    
                    # Deduplicate display
                    seen = set()
                    unique_items = []
                    for item in items:
                        txt_norm = item['text'].strip()
                        if txt_norm not in seen:
                            seen.add(txt_norm)
                            unique_items.append(item)

                    pos = [x for x in unique_items if x['label'] == 'Positive']
                    neg = [x for x in unique_items if x['label'] == 'Negative']
                    c1, c2 = st.columns(2)
                    with c1:
                        st.subheader(f"正面 ({len(pos)})")
                        # Show more items and sort by length to prioritize descriptive reviews
                        pos_sorted = sorted(pos, key=lambda x: len(x['text']), reverse=True)
                        for x in pos_sorted[:150]:
                             meta = x.get('metadata')
                             tooltip = format_tooltip(meta)
                             tag_html = "".join([f"<span class='mode-tag'>{tag}</span>" for tag in x.get('tags', [])])
                             st.markdown(f'<div class="feedback-box feedback-pos" title="{tooltip}">{tag_html}{html.escape(x["text"])}</div>', unsafe_allow_html=True)
                    with c2:
                        st.subheader(f"负面/问题 ({len(neg)})")
                        neg_sorted = sorted(neg, key=lambda x: len(x['text']), reverse=True)
                        for x in neg_sorted[:150]:
                             meta = x.get('metadata')
                             tooltip = format_tooltip(meta)
                             tag_html = "".join([f"<span class='mode-tag'>{tag}</span>" for tag in x.get('tags', [])])
                             st.markdown(f'<div class="feedback-box feedback-neg" title="{tooltip}">{tag_html}{html.escape(x["text"])}</div>', unsafe_allow_html=True)



elif menu == "📄 分析月报":
    render_hero("Monthly Analysis Report", "舆情分析月报")
    st.info("展示已生成的周期性分析报告。如需生成新报告，请在后台运行 `python main.py report`。")
    
    # Define reports directory
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports')
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
        # Also check root for legacy reports
        root_dir = os.path.dirname(os.path.dirname(__file__))
        for f in os.listdir(root_dir):
            if f.startswith("public_opinion_report_") and f.endswith(".md"):
                import shutil
                shutil.move(os.path.join(root_dir, f), os.path.join(reports_dir, f))

    # List all markdown reports
    report_files = sorted([f for f in os.listdir(reports_dir) if f.endswith(".md")], reverse=True)
    
    if not report_files:
        st.warning("暂无已生成的报告。")
    else:
        # Create a nice display name for the selector
        # e.g., public_opinion_report_202511.md -> 2025年11月 深度报告
        display_names = []
        for f in report_files:
            date_match = re.search(r'(\d{4})(\d{2})', f)
            if date_match:
                display_names.append(f"📅 {date_match.group(1)}年{date_match.group(2)}月 分析报告")
            else:
                display_names.append(f"📄 {f}")
        
        selected_display = st.selectbox("选择报告版本", display_names)
        selected_file = report_files[display_names.index(selected_display)]
        
        st.markdown("---")
        
        # Read and display the report
        report_path = os.path.join(reports_dir, selected_file)
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Display content
        st.markdown(content)
        
        # Download button
        st.download_button(
            label="📥 下载 Markdown 报告",
            data=content,
            file_name=selected_file,
            mime="text/markdown"
        )

elif menu == "🔧 配置管理":
    render_hero("System Configuration", "系统配置中心")
    
    st.subheader("🌐 爬虫源监控列表")
    st.caption(f"当前项目: {selected_game_name} ({selected_game_key})")
    st.info("此列表展示当前生效的爬虫目标链接。如需新增或修改，请编辑 `config/settings.py` 文件。")

    if selected_game_key in GAMES:
        urls = GAMES[selected_game_key].get("urls", [])
        if urls:
            for i, u in enumerate(urls):
                st.text_input(f"Source {i+1}", u, disabled=True, key=f"src_{i}")
        else:
            st.warning("暂未配置任何抓取链接。")
    else:
        st.error("无法读取当前项目配置。")
    
    st.markdown("---")

    st.subheader("🦸 英雄专项配置")
    st.info("在这里编辑游戏、英雄及其别名。")
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'heroes.json')
    
    # Load current config
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            current_config = json.load(f)
    else:
        current_config = {}
        st.warning("Config file not found, creating new.")
    
    edited_json = st.text_area("Heroes Config (JSON)", json.dumps(current_config, indent=4, ensure_ascii=False), height=400)
    
    if st.button("保存配置"):
        try:
            new_config = json.loads(edited_json)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=4, ensure_ascii=False)
            st.success("配置已保存！")
            
            # Update the global GAMES config or trigger a reload if necessary
            # For now, just confirming save. The analysis logic needs to reload this.
        except json.JSONDecodeError:
            st.error("JSON 格式错误，请检查语法。")

    st.markdown("---")
    st.subheader("🚫 停用词管理 (Stopwords)")
    st.info("在这里编辑关键词分析中需要忽略的停用词，每行一个词。")
    
    stop_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'stopwords.txt')
    current_stopwords = ""
    if os.path.exists(stop_path):
        with open(stop_path, 'r', encoding='utf-8') as f:
            current_stopwords = f.read()
    
    edited_stopwords = st.text_area("停用词列表", current_stopwords, height=300)
    
    if st.button("保存停用词"):
        try:
            with open(stop_path, 'w', encoding='utf-8') as f:
                f.write(edited_stopwords)
            st.success("停用词已保存！")
        except Exception as e:
            st.error(f"保存失败: {e}")

    st.markdown("---")
    st.subheader("📅 重大事件管理 (Events)")
    st.info("编辑用于趋势图标注的重大事件。格式为 JSON 数组，包含 name, start, end 和 color (RGBA)。")

    events_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'events.json')
    current_events_str = "[]"
    if os.path.exists(events_path):
        try:
            with open(events_path, 'r', encoding='utf-8') as f:
                events_data = json.load(f)
                current_events_str = json.dumps(events_data, indent=4, ensure_ascii=False)
        except: pass
    
    edited_events = st.text_area("事件列表 (JSON)", current_events_str, height=300)
    
    if st.button("保存事件"):
        try:
            # Validate JSON
            new_events = json.loads(edited_events)
            if not isinstance(new_events, list):
                st.error("格式错误：必须是一个 JSON 数组。")
            else:
                with open(events_path, 'w', encoding='utf-8') as f:
                    json.dump(new_events, f, indent=4, ensure_ascii=False)
                st.success("事件配置已保存！刷新总览大屏即可查看标注。")
        except json.JSONDecodeError:
            st.error("JSON 格式错误，请检查语法。")
        except Exception as e:
            st.error(f"保存失败: {e}")
    
    # Simple Preview of Events
    if os.path.exists(events_path):
        try:
            with open(events_path, 'r', encoding='utf-8') as f:
                preview_evs = json.load(f)
                if preview_evs:
                    st.write("🔍 **当前事件概览**:")
                    for ev in preview_evs:
                        st.write(f"- **{ev['name']}**: `{ev['start']}` 到 `{ev['end']}`")
        except: pass

