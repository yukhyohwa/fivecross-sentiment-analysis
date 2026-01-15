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

from core.db import get_all_data, init_db
# These were unused in the UI and causing ImportErrors due to missing/moved functions
# from core.analysis import analyze_sentiment, detailed_aspect_analysis

from config.settings import GAMES
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import jieba
import re


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
        background-color: #f0f7ff;
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
    menu = st.radio("导航", ["📊 总览大屏", "🦸 英雄专项", "⚙️ 玩法反馈", "🔎 评论探索", "🔧 配置管理"])
    st.markdown("---")
    
    # Load Data for Sidebar Filters
    df = load_data(selected_game_key)
    
    # Date Filter
    st.subheader("📅 时间筛选")
    today = pd.Timestamp.now().date()
    # Default to last 2 years (approx) or max available
    start_date = st.date_input("开始日期", today - pd.Timedelta(days=730))
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
                 # Load stopwords
                 stopwords = load_stopwords()
                 
                 wc_args = {
                    "width": 1000, 
                    "height": 400, 
                    "background_color": 'white', 
                    "collocations": False,
                    "max_words": 150,
                    "stopwords": stopwords
                 }
                 if font_path:
                     wc_args["font_path"] = font_path
                     
                 wc = WordCloud(**wc_args).generate(cut_text)
             except Exception as e:
                 st.error(f"WordCloud Error: {e}")
                 # Fallback
                 wc = WordCloud(width=1000, height=400, background_color='white', stopwords=load_stopwords()).generate(cut_text)
             
             fig_wc, ax = plt.subplots(figsize=(12, 5))
             ax.axis("off")
             st.pyplot(fig_wc)

        # NEW: Google Trends / Market Heat
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
                    
                    # Region Mapping for better display
                    region_map = {'TW': '台湾', 'HK': '香港', 'MY': '马来西亚', 'VN': '越南'}
                    t_df['region_name'] = t_df['region'].map(region_map)
                    
                    # Filtering options for Trends
                    c1, c2 = st.columns([1, 3])
                    with c1:
                        selected_kw = st.selectbox("选择热度词", t_df['keyword'].unique())
                    
                    plot_df = t_df[t_df['keyword'] == selected_kw]
                    
                    fig_trend = px.line(plot_df, x='date', y='interest_score', color='region_name',
                                       title=f"'{selected_kw}' 近期搜索热度 (100为峰值)",
                                       labels={'interest_score': '搜索热度', 'date': '日期', 'region_name': '地区'})
                    st.plotly_chart(fig_trend, use_container_width=True)
                else:
                    st.info("📊 市场趋势数据库暂无数据，请运行 google_trends.py 抓取。")
            except Exception as trend_e:
                st.error(f"趋势数据加载失败: {trend_e}")
        else:
            st.info("💡 尚未创建市场趋势数据库。")

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
                
                selected_group = st.selectbox("选择IP系列 (Anime Source)", group_names)
                
                if selected_group == "其他 - 期待联动":
                    selected_group_heroes = ungrouped_heroes
                elif selected_group != "全部":
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
                    
                    tabs = st.tabs(["💭 综合", "🗡️ 技能", "🎨 形象", "💪 强度"])
                    
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
    st.title("🔎 评论探索")
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

    st.markdown("---")
    st.subheader("🚫 停用词管理 (Stopwords)")
    st.info("在这里编辑词云中需要忽略的关键词，每行一个词。")
    
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

