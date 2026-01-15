# FiveCross Sentiment Analysis

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Playwright](https://img.shields.io/badge/Playwright-Supported-green)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-red)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

A professional public sentiment monitoring and sentiment analysis system specifically designed for "Jump Assemble" (漫画群星：大集结). It aggregates player feedback from major gaming platforms and provides deep insights via advanced NLP and interactive dashboards.

## ✨ Core Features

- **Multi-Platform Data Aggregation**:
  - **Discord Forum (Enterprise Support)**: Advanced **3-Region logic** (Sidebar -> Forum List -> Thread Details) with automatic infinite scrolling and reply extraction.
  - **TapTap (CN & Global)**: Full support for international "Post Card" data structures.
  - **YouTube**: Incremental scraping of video comments with precise source identification.
  - **QooApp**: Advanced infinite-scroll simulation for comprehensive review extraction.
  - **Bahamut Forum (Traditional Chinese)**: Specialized logic for the TW/HK community with anti-bot bypass support.
- **Advanced NLP Engine**:
  - **Hybrid Sentiment Analysis**: Integrates `SnowNLP` for granular score calculation (0.0 - 1.0) and domain-specific keyword weighting.
  - **Multi-Lingual Hero Database**: Supports massive alias mapping for Simplified Chinese, Traditional Chinese, and English.
  - **Multi-Entity Attribution**: Correctly handles clauses mentioning multiple heroes or system aspects in a single comment.
- **Hero & Gameplay Insights**:
  - **Expanded Hero Roster**: Real-time tracking for new releases like **Nobara Kugisaki (釘崎野薔薇)**, **Coyote Starrk (史塔克)**, **Minato (波風湊)**, **Luffy**, and **Sakura**.
  - **Gameplay Mode Tagging**: Automatically recognizes specific modes such as **Summit War (頂上戰爭), Mugen Train (無限列車)**, Scroll Scramble, Jujutsu High, and more.
  - **System Dimensions**: Summarizes technical feedback into Optimization, Network, Matchmaking, and Welfare.
- **Interactive Visualization**:
  - Dedicated hero feedback tabs and gameplay specific trend analysis.
  - Sentiment distribution and dynamic word clouds.

## 🚀 Getting Started

1. **Environment Setup**:

   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
2. **Launch Web Dashboard**:

   ```bash
   python main.py web
   ```
3. **Run Data Crawler**:

   ```bash
   # Crawl all platforms for the last 30 days
   python main.py crawl --days 30

   # Target a specific platform (e.g., Discord)
   python main.py crawl --source discord
   ```
4. **Execute Deep Analysis**:

   ```bash
   # Use --force to re-process all existing data with the latest NLP rules
   python main.py analyze --force
   ```

## 📂 Project Structure

```
fivecross-sentiment-analysis/
├── app/
│   └── web_ui.py          # Streamlit Analysis dashboard
├── config/
│   ├── settings.py        # Global settings and crawler targets
│   └── heroes.json        # Dynamic multi-lingual hero mapping
├── core/
│   ├── crawlers/          # Platform-specific scraping implementations (Discord, YouTube, etc.)
│   ├── analysis.py        # Sentiment engine and tag extraction logic
│   ├── crawler.py         # Crawler orchestrator
│   └── db.py              # SQLite database interface
├── data/
│   ├── jump_reviews.db    # Analysis database
│   └── discord_backup.jsonl # Raw JSONL backup
└── main.py                # Unified CLI entry point
```

## ⚙️ Configuration

- **Add Heroes**: Update `config/heroes.json`. New characters like **Starrk** or **Nobara** can be added to their respective groups.
- **Custom Mode Tags**: Add new keywords (e.g., for new seasonal modes) to the `GAME_MODES` dictionary in `core/analysis.py`.

## 📝 License

This project is for internal monitoring and analytical purposes only.
