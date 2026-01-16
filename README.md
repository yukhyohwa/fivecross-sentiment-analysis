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
- **🌍 Global Market Intelligence**:
  - **Google Trends Integration**: Automated tracking of search popularity across 6 key regions: **Taiwan, Hong Kong, Brazil, USA, Thailand, and Japan**.
- **Advanced NLP Engine**:
  - **Hybrid Sentiment Analysis**: Integrates `SnowNLP` for granular score calculation (0.0 - 1.0) and domain-specific keyword weighting.
  - **Official Announcement Filtering**: Automatically detects and sets neutral sentiment for official rules, guides, and bot messages.
  - **Multi-Entity Attribution**: Correctly handles clauses mentioning multiple heroes or system aspects in a single comment.
- **Interactive Visualization & Reporting**:
  - **Executive Dashboard**: Unified view for sentiment charts, market heat trends, and hot topic evolution.
  - **Topic Evolution**: Dynamic stacked bar charts showing how topics like **Optimization**, **Network**, and **Welfare** evolve over time, with **Day/Week/Month** aggregation support.
  - **Analysis Reports**: Dedicated section in Web UI to browse and download pre-generated monthly/periodical analysis reports.
  - **Hero Drill-down**: Detailed feedback categorization for Skill, Visual, and Strength dimensions.

## 🚀 Getting Started

1. **Environment Setup**:

   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Security Configuration**:

   Create a `.streamlit/secrets.toml` file based on the example:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
   Edit the file to set your admin username and passwords.

3. **Launch Web Dashboard**:

   ```bash
   python main.py web
   ```

4. **Sync Data & Reports**:

   ```bash
   # 1. Fetch new data
   python main.py crawl --source discord

   # 2. Run NLP analysis and AUTO-UPDATE monthly report
   python main.py analyze

   # 3. (Optional) Run only the report generator
   python main.py report
   ```

## 📂 Project Structure

```
fivecross-sentiment-analysis/
├── app/
│   └── web_ui.py          # Streamlit Analysis dashboard
├── config/
│   ├── heroes.json        # Dynamic multi-lingual hero mapping
│   ├── events.json        # Major game events timeline
│   └── stopwords.txt      # Custom keyword ignore list
├── core/
│   ├── crawlers/          # Scrapers (Discord, YouTube, Google Trends, etc.)
│   ├── analysis.py        # Sentiment engine and tag extraction logic
│   ├── db.py              # SQLite database interface
│   └── generate_sentiment_report.py # Report generation logic
├── data/
│   ├── jump_reviews.db    # Analysis database
│   └── market_trends.db   # Google Trends database
├── reports/               # Pre-generated Markdown analysis reports
└── main.py                # Unified CLI entry point
```

## ⚙️ Configuration (Accessible via Web UI)

- **Heroes mapping**: Managed via `config/heroes.json`.
- **Event Timeline**: Add major game events to `config/events.json` for trend annotation.
- **Stopwords**: Manage noise words in `config/stopwords.txt`.
- **System Aspects**: Adjust tagging logic in `core/analysis.py`.

## 📝 License

This project is for internal monitoring and analytical purposes only.
