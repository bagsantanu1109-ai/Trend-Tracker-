import os
import requests
from google import genai
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
    dataset_id = run["defaultDatasetId"] if isinstance(run, dict) else run.default_dataset_id
    items = list(client.dataset(dataset_id).iterate_items())
    return [{"caption": i.get("caption"), "audio": i.get("musicInfo", {}).get("musicName")} for i in items]

def summarize_trends(data):
    if not data:
        return "No new Instagram trends found today! 🤫"
        
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"Analyze this raw JSON from Instagram reels: {data}. Identify recurring audio tracks and themes. Write a short, punchy report for Telegram with emojis."
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt
    )
    return response.text

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    raw_data = get_instagram_trends()
    summary = summarize_trends(raw_data)
    send_telegram_message(summary)
