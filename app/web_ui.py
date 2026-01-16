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

from core.db import get_all_data, init_db
# These were unused in the UI and causing ImportErrors due to missing/moved functions
# from core.analysis import analyze_sentiment, detailed_aspect_analysis

from config.settings import GAMES
import jieba
import re
import sqlite3


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
            <h1 style="margin: 0; font-size: 2.5em; letter-spacing: 0.05em;">{title}</h1>
            <div style="height: 1px; background: #ECEAE4; width: 100px; margin: 15px 0;"></div>
            <p style="color: #666; font-size: 0.9em; text-transform: uppercase; letter-spacing: 0.1em;">{subtitle}</p>
        </div>
    """, unsafe_allow_html=True)

# Traditional Japanese Color Palette
JP_COLORS = ["#165E83", "#9F353A", "#D0AF4C", "#1B4D3E", "#70649A", "#B14B28"]

# Custom CSS
# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@400;700&family=Inter:wght@300;400;600&display=swap');
    
    .main {
        background-color: #F9F7F2; /* Soft off-white / Washi paper feel */
        color: #2D2D2D;
        font-family: 'Inter', 'Noto Sans JP', sans-serif;
    }
    
    h1, h2, h3 {
        font-family: 'Noto Serif JP', serif;
        color: #1A1A1A;
        font-weight: 700 !important;
    }
    
    .stMetric {
        background-color: #ffffff;
        padding: 20px;
        border: 1px solid #ECEAE4;
        border-radius: 4px; /* Sharper, more minimalist */
        box-shadow: none;
    }
    
    .stSidebar {
        background-color: #FFFFFF !important;
        border-right: 1px solid #ECEAE4;
    }
    
    .hero-box {
        background: #FFFFFF;
        padding: 20px;
        border-left: 5px solid #9F353A; /* Enji - traditional crimson accent */
        margin-bottom: 30px;
        border-radius: 2px;
    }

    /* Existing App Specific Styles */
    .feedback-box {
        border-left: 4px solid #ddd;
        padding: 10px;
        margin: 5px 0;
        background-color: #ffffff; /* Changed to white to match new theme */
        color: #333;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05); /* Slight shadow for depth */
    }
    .feedback-pos { border-left-color: #2ecc71; }
    .feedback-neg { border-left-color: #e74c3c; }
    .mode-tag {
        display: inline-block;
        padding: 2px 8px;
        margin: 2px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: bold;
        background-color: #e0f2fe;
        color: #0369a1;
        border: 1px solid #bae6fd;
    }
    .feedback-box:hover {
        background-color: #f8f9fa;
        cursor: help;
        border-left-width: 6px;
        transition: all 0.2s;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=60)
def load_data(game_filter=None):
    init_db()
    df = get_all_data()
    if not df.empty:
        if 'review_date' in df.columns:
            df['review_date'] = pd.to_datetime(df['review_date'], errors='coerce')
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
    menu = st.radio("导航", ["📊 总览大屏", "🦸 英雄专项", "⚙️ 玩法反馈", "🔎 评论探索", "📄 分析月报", "🔧 配置管理"])
    st.markdown("---")
    
    # Load Data for Sidebar Filters
    df = load_data(selected_game_key)
    
    # Date Filter
    st.subheader("📅 时间筛选")
    today = pd.Timestamp.now().date()
    # Default to last 1 year
    start_date = st.date_input("开始日期", today - pd.Timedelta(days=365))
    end_date = st.date_input("结束日期", today)
    
    # Source Filter
    st.subheader("🌐 来源筛选")
    all_sources = sorted(list(df['source'].dropna().unique())) if 'source' in df.columns else []
    selected_sources = st.multiselect("选择来源", all_sources, default=all_sources)
    
    if "taptap_intl" in selected_sources:
        pass

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
    """Load mapping of Hero Code -> IP Group Name based on heroes.json"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'heroes.json')
    hero_ip_map = {} # HeroCode -> IPName
    ip_hero_list = {} # IPName -> [HeroCodes]
    
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
                        for c in codes:
                            hero_ip_map[c] = g_name
        except Exception as e:
            print(f"Error loading hero map: {e}")
            
    return hero_ip_map, ip_hero_list

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
                             color_discrete_map={'Positive':'#2ecc71', 'Negative':'#e74c3c', 'Neutral':'#95a5a6'})
                fig.update_layout(font_family="Inter", title_font_family="Noto Serif JP")
                st.plotly_chart(fig, use_container_width=True)
        
        with c2:
            st.subheader("⭐ 评分分布")
            if 'rating' in df.columns:
                rc = df['rating'].value_counts().sort_index().reset_index()
                rc.columns = ['Star', 'Count']
                rc['Star'] = rc['Star'].replace({0: '期待/0星'})
                fig_star = px.bar(rc, x='Star', y='Count', 
                                 template="plotly_white")
                fig_star.update_traces(marker_color=JP_COLORS[0], marker_line_color='#bcaf9f', marker_line_width=1)
                fig_star.update_layout(
                    height=300,
                    font_family="Inter", title_font_family="Noto Serif JP",
                    margin=dict(t=20, b=20, l=20, r=20),
                    xaxis=dict(title=None),
                    yaxis=dict(title=None)
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
                height=350,
                template='plotly_white',
                font_family="Inter", title_font_family="Noto Serif JP",
                hovermode='x unified',
                margin=dict(t=30, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
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
                                    labels={'date': '日期', 'mentions': '提及次', 'topic': '话题'})
                    fig_bar.update_layout(
                        height=400,
                        font_family="Inter", title_font_family="Noto Serif JP",
                        margin=dict(t=10, b=0, l=0, r=0),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        xaxis=dict(title=None),
                        yaxis=dict(title="提及频次")
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
        st.subheader("🚀 热词飙升榜 (Anomaly Detection)")
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
                    for txt in dataframe['content'].dropna():
                        # Filter: only Chinese/English words, length > 1
                        words = [w for w in jieba.cut(str(txt)) if len(w) > 1 and w not in stopwords and not re.match(r'^[0-9.]+$', w)]
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



        # 3. Google Trends / Market Heat
        st.markdown("---")
        st.subheader("🌍 市场热度趋势 (Google Trends)")
        
        TRENDS_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'market_trends.db')
        if os.path.exists(TRENDS_DB):
            try:
                t_conn = sqlite3.connect(TRENDS_DB)
                t_df = pd.read_sql_query("SELECT * FROM google_trends", t_conn)
                t_conn.close()
                
                if not t_df.empty:
                    t_df['date'] = pd.to_datetime(t_df['date'])
                    
                    # Filter for last 3 months (90 days)
                    three_months_ago = pd.Timestamp.now() - pd.Timedelta(days=90)
                    t_df = t_df[t_df['date'] >= three_months_ago]
                    
                    # Region Mapping for better display
                    region_map = {
                        'TW': '台湾', 'HK': '香港', 
                        'US': '美国', 
                        'TH': '泰国', 'JP': '日本'
                    }

                    t_df['region_name'] = t_df['region'].map(region_map)
                    
                    # Filtering options for Trends
                    c1, c2 = st.columns([1, 3])
                    with c1:
                        selected_kw = st.selectbox("选择热度词", t_df['keyword'].unique())
                    
                    plot_df = t_df[t_df['keyword'] == selected_kw]
                    
                    fig_trend = px.line(plot_df, x='date', y='interest_score', color='region_name',
                                       title=f"'{selected_kw}' 近期搜索热度 (100为峰值)",
                                       color_discrete_sequence=JP_COLORS,
                                       labels={'interest_score': '搜索热度', 'date': '日期', 'region_name': '地区'})
                    fig_trend.update_layout(font_family="Inter", title_font_family="Noto Serif JP")
                    st.plotly_chart(fig_trend, use_container_width=True)
                else:
                    st.info("📊 市场趋势数据库暂无数据，请运行 google_trends.py 抓取。")
            except Exception as trend_e:
                st.error(f"趋势数据加载失败: {trend_e}")
        else:
            st.info("💡 尚未创建市场趋势数据库。")

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
            
            # stragglers/others logic (if any are left that we actually want)
            ungrouped_heroes = [] # Force empty as we don't want to show unconfigured IPs

            if hero_groups:
                # Groups are sorted keys now
                group_names = ["全部"] + sorted(list(hero_groups.keys()))
                
                # Add "Others" option if there are stragglers
                if ungrouped_heroes:
                    group_names.append("其他 - 期待联动")
                
                # Side-by-side selector layout
                f_c1, f_c2 = st.columns(2)
                
                with f_c1:
                    selected_group = st.selectbox("选择IP系列 (Anime Source)", group_names)
                
                # Filter Logic
                if selected_group == "其他 - 期待联动":
                    selected_group_heroes = ungrouped_heroes
                elif selected_group != "全部":
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
                    hero_ip_map, _ = load_hero_ip_map(selected_game_key)
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
                            
                            fig_h.update_layout(
                                title=f"{display_map.get(selected_hero_code, selected_hero_code)} - 热度与情感走势",
                                xaxis=dict(title=None),
                                yaxis=dict(title='热度', showgrid=False),
                                yaxis2=dict(title='情感', overlaying='y', side='right', range=[0, 1], showgrid=True),
                                font_family="Inter", title_font_family="Noto Serif JP",
                                hovermode='x unified',
                                height=350,
                                template='plotly_white'
                            )
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
                            for txt in hero_texts:
                                words = [w for w in jieba.cut(txt) if len(w) > 1 and w not in stopwords and not re.match(r'^[0-9.]+$', w)]
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
        for json_str in df['detailed_analysis'].dropna():
            try:
                data = json.loads(json_str)
                system = data.get("System", {})
                for aspect, items in system.items():
                    if aspect not in sys_data: sys_data[aspect] = []
                    sys_data[aspect].extend(items)
            except:
                pass
            
        tabs = st.tabs(sorted(sys_data.keys())) if sys_data else []
        if not tabs:
            st.warning("暂无系统层面的反馈。")
        else:
            for i, aspect in enumerate(sorted(sys_data.keys())):
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


elif menu == "🔎 评论探索":
    render_hero("Comment Explorer", "评论探索")
    if not df.empty:
        search = st.text_input("搜索内容")
        filtered_df = df
        if search:
            filtered_df = df[df['content'].str.contains(search, na=False, case=False)]
        
        st.write(f"共 {len(filtered_df)} 条")
        for idx, row in filtered_df.head(20).iterrows():
            source_badge = f"**[{row.get('source', 'Unknown')}]**"
            date_display = str(row.get('review_date', '')).split(' ')[0]
            st.markdown(f"{source_badge} **{row.get('author','Unknown')}** | {date_display}")
            
            # Content Info
            c_title = row.get('content_title', '')
            c_url = row.get('content_url', '')
            
            if c_title:
                st.markdown(f"📺 *Source*: [{c_title}]({c_url})")
                
            st.write(row.get('content'))
            st.markdown("---")

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

