# 🚀 AI-Powered Instagram Trend Tracker to Telegram

This project is a 100% free, fully automated pipeline that scrapes recent Instagram reels for trending audio and themes, analyzes the raw data using an AI model, and delivers a concise summary report directly to your phone via Telegram.

## 🛠️ Architecture & Tech Stack

This project utilizes the generous free tiers of several developer platforms to run continuously at zero cost.

*   **Data Extraction (Apify):** Uses the Apify Instagram Scraper to bypass anti-bot protections and extract reel data (captions, audio tracks, view counts).
*   **AI Processing (Google Gemini):** Processes the raw, noisy JSON data to identify actual trends and write a human-readable summary.
*   **Delivery (Telegram Bot API):** Pushes the AI-generated report to your personal Telegram chat.
*   **Automation (GitHub Actions):** Runs a Python script on a schedule (Cron job) using free cloud compute minutes.

## 🔑 Prerequisites

Before setting up the repository, you will need to create accounts and gather four API keys:

1.  **Apify API Token:** Sign up at [Apify](https://apify.com/), navigate to Settings > Integrations, and generate a personal API token.
2.  **Google Gemini API Key:** Go to [Google AI Studio](https://aistudio.google.com/) and create a free API key.
3.  **Telegram Bot Token:** Message `@BotFather` on Telegram, send `/newbot`, follow the prompts, and copy the provided HTTP API token.
4.  **Telegram Chat ID:** Send a message to your new bot, then visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates` in your browser to find your `chat_id`.

## 📂 Project Structure

Your project requires two files. 

### 1. `main.py`
This is the core Python script that orchestrates the APIs. Place this in the root of your repository.

```python
import os
import requests
import google.generativeai as genai
from apify_client import ApifyClient

APIFY_TOKEN = os.environ.get("APIFY_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def get_instagram_trends():
    client = ApifyClient(APIFY_TOKEN)
    run_input = {
        "hashtags": ["trendingaudio", "instatrends"],
        "resultsLimit": 20, 
    }
    run = client.actor("apify/instagram-scraper").call(run_input=run_input)
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    return [{"caption": i.get("caption"), "audio": i.get("musicInfo", {}).get("musicName")} for i in items]

def summarize_trends(data):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"Analyze this raw JSON from Instagram reels: {data}. Identify recurring audio tracks and themes. Write a short, punchy report for Telegram with emojis."
    response = model.generate_content(prompt)
    return response.text

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    raw_data = get_instagram_trends()
    summary = summarize_trends(raw_data)
    send_telegram_message(summary)
```

### 2. `.github/workflows/schedule.yml`
This file configures GitHub Actions to run the script automatically every day. Create a folder named `.github`, inside it create a folder named `workflows`, and place this file there.

```yaml
name: Daily Instagram Trend Report

on:
  schedule:
    - cron: '0 8 * * *' # Runs at 8:00 AM UTC daily
  workflow_dispatch:

jobs:
  run-bot:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: pip install apify-client google-generativeai requests

      - name: Run Trend Pipeline
        env:
          APIFY_TOKEN: ${{ secrets.APIFY_TOKEN }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python main.py
```

## ⚙️ Deployment Instructions

1.  Create a **Private Repository** on GitHub.
2.  Upload `main.py` and the `.github/workflows/schedule.yml` file to the repository.
3.  Navigate to **Settings > Secrets and variables > Actions**.
4.  Add the following **New repository secrets**:
    *   `APIFY_TOKEN`
    *   `GEMINI_API_KEY`
    *   `TELEGRAM_BOT_TOKEN`
    *   `TELEGRAM_CHAT_ID`
5.  Go to the **Actions** tab in your repository.
6.  Select "Daily Instagram Trend Report" on the left menu.
7.  Click **Run workflow** to test the setup. 

If everything is configured correctly, you will receive a Telegram message with the latest trends within a minute or two!