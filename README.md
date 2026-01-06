# FiveCross Sentiment Analysis (舆情监控系统)

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Playwright](https://img.shields.io/badge/Playwright-Supported-green)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-red)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

A comprehensive sentiment analysis and monitoring system focusing on game reviews from multiple platforms (TapTap CN, TapTap Intl, YouTube, QooApp). Primarily built for "Jump Assemble" (漫画群星：大集结) but extensible for other games.

## ✨ Features

- **Multi-Source Crawler**:
  - **TapTap CN**: Captures reviews from the Chinese store.
  - **TapTap Intl (Global)**: Supports international reviews with updated "Post Card" structure.
  - **YouTube**: Incrementally scrapes recent videos and their comments.
  - **QooApp**: Supports deep scraping via infinite scroll and "View More" handling.
- **Smart Data Processing**:
  - **Data Normalization**: Standardizes dates (relative "1 year ago" -> "YYYY-MM-DD").
  - **Incremental Updates**: Efficiently fetches only new reviews based on time windows.
  - **Metadata Tracking**: Steps original source text and related video info (for YouTube).
- **Advanced Analysis**:
  - **Sentiment Analysis**: Classifies feedback (Positive/Negative/Neutral) using NLP.
  - **Aspect Mining**: Extracts keywords related to Heroes (e.g., Goku, Luffy) and System (e.g., Lag, Matchmaking).
  - **Visualization**: Interactive charts for trends, word clouds, and rating distributions.

## 🚀 Installation

1.  **Clone the repository**:
    ```bash
    git clone <your-repo-url>
    cd fivecross-sentiment-analysis
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Install Playwright browsers**:
    ```bash
    playwright install chromium
    ```

## 🖥️ Usage

The project provides a unified entry point `main.py` with multiple modes.

### 1. Interactive Menu (Default)
Simply run the script to choose a mode:
```bash
python main.py
```

### 2. Analysis Dashboard (Web UI)
Launch the visual dashboard to explore data:
```bash
python main.py web
# or
streamlit run app/web_ui.py
```

### 3. Crawler (CLI)
Run the crawler to fetch new data.
- **Default (Default 2 years)**:
  ```bash
  python main.py crawl
  ```
- **Incremental (Last 30 days)**:
  ```bash
  python main.py crawl --days 30
  ```

### 4. Analysis Process
Re-run NLP analysis on existing database records:
```bash
python main.py analyze
```

## 📂 Project Structure

```
fivecross-sentiment-analysis/
├── app/
│   └── web_ui.py          # Streamlit Dashboard application
├── config/
│   ├── settings.py        # Crawler & Game configurations
│   └── heroes.json        # Dynamic hero mapping configuration
├── core/
│   ├── crawlers/          # Platform-specific crawler modules
│   │   ├── base.py        # Shared utilities (saving, date parsing)
│   │   ├── taptap_cn.py
│   │   ├── taptap_intl.py
│   │   ├── youtube.py
│   │   └── qooapp.py
│   ├── analysis.py        # NLP & Sentiment analysis logic
│   ├── crawler.py         # Crawler dispatcher/orchestrator
│   └── db.py              # SQLite database operations
├── data/
│   └── jump_reviews.db    # SQLite Database file
├── main.py                # Main CLI entry point
└── requirements.txt       # Project dependencies
```

## ⚙️ Configuration

- **Game/URL Settings**: Modify `config/settings.py` to add new games or change target URLs.
- **Hero Mappings**: Update `config/heroes.json` to track new characters or keywords.

## 📝 License

This project is for internal use and monitoring purposes.
