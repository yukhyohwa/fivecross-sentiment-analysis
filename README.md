# Jump Assemble Review Monitor (漫画群星：大集结 舆情监控)

This project is a sentiment analysis and monitoring system for "Jump Assemble" (JUMP：群星集结) reviews from TapTap.

## Features
1.  **Crawler**: Simulates a real user to scrape reviews from [TapTap](https://www.taptap.cn/app/358933/review) using `playwright`.
2.  **Database**: Stores reviews in a local SQLite database (`jump_reviews.db`).
3.  **Analysis**:
    -   **Sentiment Analysis**: Uses `snownlp` to classify reviews as Positive, Negative, or Neutral.
    -   **Keyword Extraction**: Identifies mentions of specific characters (e.g., Goku, Naruto, Luffy) and game aspects (Lag, Graphics).
    -   **Trending**: Generates charts for rating distribution and sentiment.

## Installation

1.  Install Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```
2.  Install Playwright browsers:
    ```bash
    playwright install chromium
    ```

## Usage

### Web Dashboard (Recommended)
Launch the interactive dashboard to view data and control the crawler:
```bash
streamlit run app.py
```
This will open a web interface in your browser where you can:
-   View real-time sentiment analysis and charts.
-   Explore individual reviews with filtering.
-   Start the crawler directly from the "Crawler Control" tab.

### CLI Mode (Optional)
Run the script solely from the command line:
```bash
python main.py
```
This will:
1.  Launch a browser window and scrape the latest 50 reviews (configurable).
2.  Save them to the database.
3.  Perform sentiment analysis and character extraction on new reviews.
4.  Generate report images (`rating_dist.png`, `sentiment_dist.png`, `review_trend.png`) and print a summary to the console.

## Project Structure
-   `crawler.py`: Handles scraping.
-   `analysis.py`: Handles data processing and visualization.
-   `db.py`: Database schema and operations.
-   `main.py`: Main entry point.
