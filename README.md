# FiveCross Sentiment Analysis

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Playwright](https://img.shields.io/badge/Playwright-Supported-green)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-red)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

A professional public sentiment monitoring and sentiment analysis system specifically designed for "Jump Assemble" (漫画群星：大集结). It aggregates player feedback from major gaming platforms and provide deep insights via advanced NLP and interactive dashboards.

## ✨ Core Features

- **Multi-Platform Data Aggregation**:
  - **Discord Community (Local Sync)**: Specialized logic to import and clean exported Discord TXT chat logs. Filters system messages and bot commands automatically.
  - **TapTap (CN & Global)**: Full support for international "Post Card" data structures.
  - **YouTube**: Incremental scraping of video comments with precise source identification.
  - **QooApp**: Advanced infinite-scroll simulation for comprehensive review extraction.
  - **Bahamut Forum (Traditional Chinese)**: Specialized logic for the TW/HK community with anti-bot bypass support.
- **🧠 Advanced NLP & Sentiment Engine**:
  - **Refinement Sentiment Analysis**: Hybrid `SnowNLP` + domain-specific rule engine. Optimized for gaming slang (e.g., "骗氪", "拉胯", "寄了", "傻逼").
  - **Local AI Engine (Gemma 4)**: Support for fully offline semantic analysis and tagging using a local llama-server. No API fees or data privacy concerns.
  - **Semantic Panorama**: Visualizes public opinion and dynamically organizes community chats and reviews using **Gemma 4** or **Google Gemini 2.0** embeddings.
  - **Official Announcement Filtering**: Robust detection of official rules and bot messages.
  - **Multi-Entity Attribution**: Clause-level sentiment analysis for precise tagging of heroes or system aspects.
- **Interactive Visualization & Reporting**:
  - **Executive Dashboard**: Unified view for sentiment charts and hot topic evolution.
  - **Analysis Reports**: Web-based viewer for monthly Markdown reports.

## 🚀 Getting Started

1. **Environment Setup**:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **AI Configuration (Pick one)**:
   - **Cloud (Gemini)**: Set `GEMINI_API_KEY` in `.env`.
   - **Local (Gemma 4)**: Ensure the local inference server (llama-server) is running at `127.0.0.1:8080`, then run `python scripts/process_local_gemma.py`.

3. **Launch Web Dashboard**:
   ```bash
   python main.py web
   ```

4. **Sync Data & Reports**:
   ```bash
   # 1. Fetch new data (Reviews + Discord Local Import)
   python main.py crawl
   ```

## 📂 Project Structure

```
fivecross-sentiment-analysis/
├── bin/
│   └── llama-cpp/         # Local AI Inference Kernels
├── app/
│   └── web_ui.py          # Streamlit Analysis dashboard
├── config/
│   ├── heroes.json        # Hero & IP mapping
│   ├── events.json        # Game events timeline
│   └── stopwords.txt      # Custom keyword ignore list
├── core/
│   ├── crawlers/          # Scrapers (Bahamut, TapTap, YouTube, etc.)
│   ├── utils/             # Helpers (Discord TXT Importer)
│   ├── analysis.py        # Sentiment engine
│   ├── db.py              # SQLite database interface (Reviews & Chats)
│   └── generate_sentiment_report.py
├── data/
│   ├── jump_reviews.db    # Review database
│   └── jump_chats.db      # Community chat database
├── reports/               # Markdown analysis reports
├── scripts/
│   ├── import_discord.py  # Standalone chat importer
│   └── process_local_gemma.py # Local AI Analysis Pipeline
└── main.py                # Unified CLI entry point
```

## 📝 License
This project is for internal monitoring and analytical purposes only.
