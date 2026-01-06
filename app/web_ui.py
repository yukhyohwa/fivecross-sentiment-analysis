import streamlit as st
import os
import sys

# Add project root to path for Streamlit Cloud
# Use insert(0) to ensure this path takes precedence
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import time
import io

from core.db import get_all_data, init_db
from core.analysis import analyze_sentiment, extract_keywords, detailed_aspect_analysis, update_analysis_results
import core.crawler as crawler
from config.settings import GAMES
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import jieba
import re

# Page Configuration
st.set_page_config(
    page_title="Multi-Game Monitor",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
    }
    .feedback-box {
        border-left: 4px solid #ddd;
        padding: 10px;
        margin: 5px 0;
        background-color: #f9f9f9;
        color: #333;
    }
    .feedback-pos { border-left-color: #2ecc71; }
    .feedback-neg { border-left-color: #e74c3c; }
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

def run_spider_ui(game_key, max_count):
    output_buffer = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = output_buffer
    try:
        with st.spinner(f"正在爬取 {GAMES[game_key]['name']}..."):
            crawler.run_crawler(game_key, max_count)
            
            # Re-process
            from db import get_reviews_for_analysis
            rows = get_reviews_for_analysis(game_key)
            for r in rows:
                rid, content, gid = r
                if not content: continue
                gid = gid if gid else game_key
                score, label = analyze_sentiment(content)
                mentions = extract_keywords(content, gid)
                details = detailed_aspect_analysis(content, gid)
                update_analysis_results(rid, score, label, mentions, details)
            st.success("完成！")
    except Exception as e:
        st.error(f"Error: {e}")
    finally:
        sys.stdout = original_stdout
    return output_buffer.getvalue()

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
    
    # Date Filter
    st.subheader("📅 时间筛选")
    today = pd.Timestamp.now().date()
    # Default to last 2 years (approx) or max available
    start_date = st.date_input("开始日期", today - pd.Timedelta(days=730))
    end_date = st.date_input("结束日期", today)
    
    menu = st.radio("导航", ["📊 总览大屏", "🦸 英雄专项", "⚙️ 玩法反馈", "🔎 评论探索", "🕷️ 爬虫控制", "🔧 配置管理"])
    st.markdown("---")

df = load_data(selected_game_key)

# Apply Date Filter
if not df.empty and 'review_date' in df.columns:
    # Convert inputs to datetime
    s_dt = pd.to_datetime(start_date)
    e_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1) # End of day
    
    mask = (df['review_date'] >= s_dt) & (df['review_date'] <= e_dt)
    df = df.loc[mask]

if menu == "📊 总览大屏":
    st.title(f"📊 {selected_game_name} - 舆情总览")
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
            st.subheader("情感倾向")
            if 'sentiment_label' in df.columns:
                counts = df['sentiment_label'].value_counts().reset_index()
                counts.columns = ['Label', 'Count']
                fig = px.pie(counts, values='Count', names='Label', color='Label',
                             color_discrete_map={'Positive':'#2ecc71', 'Negative':'#e74c3c', 'Neutral':'#95a5a6'})
                st.plotly_chart(fig, use_container_width=True)
        
        with c2:
            st.subheader("评分分布")
            if 'rating' in df.columns:
                rc = df['rating'].value_counts().sort_index().reset_index()
                rc.columns = ['Star', 'Count']
                rc['Star'] = rc['Star'].replace({0: '期待/0星'})
                fig = px.bar(rc, x='Star', y='Count', color='Count')
                st.plotly_chart(fig, use_container_width=True)

        # Word Cloud
        st.markdown("---")
        st.subheader("☁️ 评论词云 (Word Cloud)")
        if 'content' in df.columns and not df['content'].dropna().empty:
             full_text = " ".join(df['content'].dropna().astype(str))
             # Chinese segmentation
             cut_text = " ".join(jieba.cut(full_text))
             
             # Font Selection logic for Cloud/Local
             font_path = None
             potential_paths = [
                 "C:/Windows/Fonts/msyh.ttc", # Windows
                 "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", # Linux (Debian/Ubuntu) - ZenHei
                 "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", # Linux Noto
                 "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"
             ]
             
             for p in potential_paths:
                 if os.path.exists(p):
                     font_path = p
                     break
             
             try:
                 wc_args = {
                    "width": 1000, 
                    "height": 400, 
                    "background_color": 'white', 
                    "collocations": False,
                    "max_words": 150
                 }
                 if font_path:
                     wc_args["font_path"] = font_path
                     
                 wc = WordCloud(**wc_args).generate(cut_text)
             except Exception as e:
                 st.error(f"WordCloud Error: {e}")
                 # Fallback
                 wc = WordCloud(width=1000, height=400, background_color='white').generate(cut_text)
             
             fig_wc, ax = plt.subplots(figsize=(12, 5))
             ax.imshow(wc, interpolation='bilinear')
             ax.axis("off")
             st.pyplot(fig_wc)

elif menu == "🦸 英雄专项":
    st.title("🦸 英雄专项反馈")
    
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
                             hero_groups = fc[selected_game_key]["Groups"]
                except: pass

            # Create a display map: CodeName -> Display Name (Chinese)
            display_map = {}
            keywords = GAMES[selected_game_key].get('keywords', {})
            
            # Pre-fill with CodeName
            for h_code in hero_data.keys():
                display_map[h_code] = h_code 
                
            # Try to find a Chinese alias
            for h_code in hero_data.keys():
                aliases = [k for k, v in keywords.items() if v == h_code]
                chinese_aliases = [a for a in aliases if not re.search('[a-zA-Z]', a)]
                if chinese_aliases:
                   display_map[h_code] = chinese_aliases[0]
                elif aliases:
                   display_map[h_code] = aliases[0]
            
            # Group Selection
            selected_group_heroes = list(hero_data.keys())
            if hero_groups:
                group_names = ["全部"] + list(hero_groups.keys())
                selected_group = st.selectbox("选择IP系列 (Anime Source)", group_names)
                
                if selected_group != "全部":
                    # Filter heroes belonging to this group
                    allowed_heroes = set(hero_groups[selected_group])
                    selected_group_heroes = [h for h in hero_data.keys() if h in allowed_heroes]
            
            if not selected_group_heroes:
                st.warning("该系列暂无相关反馈数据的英雄。")
            else:
                # Sort by Display Name
                sorted_heroes = sorted(selected_group_heroes, key=lambda x: display_map.get(x, x))
                
                selected_hero_code = st.selectbox("选择角色", sorted_heroes, format_func=lambda x: display_map.get(x, x))
                
                if selected_hero_code:
                    st.subheader(f"⚔️ {display_map.get(selected_hero_code, selected_hero_code)}")
                    dims = hero_data[selected_hero_code]
                    
                    tabs = st.tabs(["🗡️ 技能", "🎨 形象", "💪 强度"])
                    
                    def render_feedback(dimension_key, tab_container):
                        with tab_container:
                            items = dims.get(dimension_key, [])
                            if not items:
                                st.caption("暂无相关反馈")
                                return
                            
                            pos = [i for i in items if i['label'] == 'Positive']
                            neg = [i for i in items if i['label'] == 'Negative']
                            
                            c1, c2 = st.columns(2)
                            with c1:
                                st.write(f"🙂 好评 ({len(pos)})")
                                for p in pos:
                                    st.markdown(f"<div class='feedback-box feedback-pos'>{p['text']}</div>", unsafe_allow_html=True)
                            with c2:
                                st.write(f"😡 差评/建议 ({len(neg)})")
                                for n in neg:
                                    st.markdown(f"<div class='feedback-box feedback-neg'>{n['text']}</div>", unsafe_allow_html=True)
                    
                    render_feedback("Skill", tabs[0])
                    render_feedback("Visual", tabs[1])
                    render_feedback("Strength", tabs[2])

elif menu == "⚙️ 玩法反馈":
    st.title("⚙️ 玩法与系统反馈")
    
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
                    pos = [x for x in items if x['label'] == 'Positive']
                    neg = [x for x in items if x['label'] == 'Negative']
                    c1, c2 = st.columns(2)
                    with c1:
                        st.subheader(f"正面 ({len(pos)})")
                        for x in pos[:20]:
                             st.markdown(f"<div class='feedback-box feedback-pos'>{x['text']}</div>", unsafe_allow_html=True)
                    with c2:
                        st.subheader(f"负面/问题 ({len(neg)})")
                        for x in neg[:20]:
                             st.markdown(f"<div class='feedback-box feedback-neg'>{x['text']}</div>", unsafe_allow_html=True)

elif menu == "🔎 评论探索":
    st.title("🔎 评论探索")
    if not df.empty:
        search = st.text_input("搜索内容")
        filtered_df = df
        if search:
            filtered_df = df[df['content'].str.contains(search, na=False, case=False)]
        
        st.write(f"共 {len(filtered_df)} 条")
        for idx, row in filtered_df.head(20).iterrows():
            st.markdown(f"**{row.get('author','Unknown')}** | {str(row.get('review_date', '')).split(' ')[0]}")
            st.write(row.get('content'))
            st.markdown("---")

elif menu == "🕷️ 爬虫控制":
    st.title("🕷️ 爬虫控制台")
    st.info(f"即将抓取项目: **{selected_game_name}**")
    
    months = st.slider("抓取时间范围 (过去 N 个月)", 1, 60, 24)
    
    if st.button("开始抓取", type="primary"):
        with st.status("正在运行爬虫...", expanded=True) as status:
            log = run_spider_ui(selected_game_key, months)
            st.text_area("日志", log)
            status.update(label="抓取完成", state="complete")
        
        time.sleep(1)
        st.experimental_rerun()

elif menu == "🔧 配置管理":
    st.title("🔧 英雄配置管理")
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'heroes.json')
    
    # Load current config
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            current_config = json.load(f)
    else:
        current_config = {}
        st.warning("Config file not found, creating new.")

    # Show JSON editor
    st.subheader("编辑 JSON 配置")
    st.info("在这里手动添加游戏、英雄及其别名。")
    
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

