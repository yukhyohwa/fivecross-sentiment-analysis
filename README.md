# FiveCross Sentiment Analysis

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Playwright](https://img.shields.io/badge/Playwright-Supported-green)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-red)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

A professional public sentiment monitoring and sentiment analysis system specifically designed for "Jump Assemble" (漫画群星：大集结). It aggregates player feedback from major gaming platforms and provides deep insights via advanced NLP and interactive dashboards.

## ✨ Core Features

- **Multi-Platform Data Aggregation**:
  - **TapTap (CN & Global)**: Full support for international "Post Card" data structures.
  - **YouTube**: Incremental scraping of video comments with precise source identification.
  - **QooApp**: Advanced infinite-scroll simulation for comprehensive review extraction.
  - **Bahamut Forum (Traditional Chinese)**: Specialized logic for the TW/HK community with anti-bot bypass support.
- **Advanced NLP Engine**:
  - **Hybrid Sentiment Analysis**: Integrates `SnowNLP` for granular score calculation (0.0 - 1.0) and domain-specific keyword weighting.
  - **Multi-Lingual Hero Database**: Supports massive alias mapping for Simplified Chinese, Traditional Chinese, and English (e.g., Goku / 孫悟空 / 悟空).
  - **Multi-Entity Attribution**: Correctly handles clauses mentioning multiple heroes or system aspects in a single comment.
- **Hero & Gameplay Insights**:
  - **Hero Monitoring**: Track feedback for every hero across dimensions like Skills, Strength, and Visuals.
  - **Gameplay Mode Tagging**: Automatically recognizes specific modes such as **Summit War, Scroll Scramble, Mugen Train, Jujutsu High, Martial Arts Tournament, Duo/Solo Brawl**.
  - **System Dimensions**: Summarizes technical feedback into **Optimization, Network, Matchmaking, and Welfare**.
- **Interactive Visualization**:
  - Dedicated hero feedback tabs.
  - Gameplay specific trend analysis.
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
   # Crawl data from the last 7 days
   python main.py crawl --days 7
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
│   ├── crawlers/          # Platform-specific scraping implementations
│   ├── analysis.py        # Sentiment engine and tag extraction logic
│   ├── crawler.py         # Crawler orchestrator
│   └── db.py              # SQLite database interface
├── data/
│   └── jump_reviews.db    # Sentiment database
└── main.py                # Unified CLI entry point
```

## ⚙️ Configuration

- **Add Heroes**: Update `config/heroes.json`. The first alias in the list is used as the primary display name in the UI.
- **Custom Mode Tags**: Add new keywords to the `GAME_MODES` dictionary in `core/analysis.py`.

## 📝 License

This project is for internal monitoring and analytical purposes only.
