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

# A list of Chat IDs to broadcast to. 
# We include the ones from the environment variable (if any), plus the hardcoded ones.
ENV_CHAT_IDS = [x.strip() for x in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if x.strip()]
BROADCAST_CHAT_IDS = set(ENV_CHAT_IDS + ["8300734497", "1326228475"])

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    for chat_id in BROADCAST_CHAT_IDS:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        try:
            res = requests.post(url, json=payload)
            if res.status_code != 200:
                print(f"Failed to send Markdown to {chat_id}: {res.text}. Trying plain text...")
                # Fallback to plain text
                payload = {"chat_id": chat_id, "text": text}
                res2 = requests.post(url, json=payload)
                if res2.status_code == 200:
                    print(f"Sent plain text message to {chat_id}")
                else:
                    print(f"Completely failed to send to {chat_id}: {res2.text}")
            else:
                print(f"Sent message to {chat_id}")
        except Exception as e:
            print(f"Failed to send to {chat_id}: {e}")

if __name__ == "__main__":
    raw_data = get_instagram_trends()
    summary = summarize_trends(raw_data)
    send_telegram_message(summary)
