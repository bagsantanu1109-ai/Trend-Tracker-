import os
import requests
from apify_client import ApifyClient
from datetime import datetime, timezone, timedelta
import random
import re

APIFY_TOKEN = os.environ.get("APIFY_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

ENV_CHAT_IDS = [x.strip() for x in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if x.strip()]
BROADCAST_CHAT_IDS = set(ENV_CHAT_IDS + ["8300734497", "1326228475"])

def get_instagram_trends():
    client = ApifyClient(APIFY_TOKEN)
    
    try:
        with open("target_profiles.txt", "r") as f:
            profiles = [line.strip() for line in f if line.strip()]
    except Exception:
        profiles = ["https://www.instagram.com/instagram/"]
        
    print(f"Scraping profiles: {profiles}")

    run_input = {
        "directUrls": profiles,
        "resultsLimit": 20, 
    }
    run = client.actor("apify/instagram-scraper").call(run_input=run_input)
    dataset_id = run["defaultDatasetId"] if isinstance(run, dict) else run.default_dataset_id
    items = list(client.dataset(dataset_id).iterate_items())
    
    now = datetime.now(timezone.utc)
    filtered = []
    
    for i in items:
        if i.get("productType") != "clips" and not i.get("isVideo"):
            continue
            
        ts_str = i.get("timestamp")
        if ts_str:
            try:
                dt = datetime.strptime(ts_str.split(".")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                if now - dt > timedelta(days=7):
                    continue
            except Exception:
                pass

        views = i.get("videoViewCount") or i.get("playCount") or i.get("viewCount") or 0
        likes = i.get("likesCount") or 0
        comments = i.get("commentsCount") or 0
        short_code = i.get("shortCode") or i.get("url", "").rstrip("/").split("/")[-1]
        caption = i.get("caption", "")
        
        filtered.append({
            "url": f"https://www.instagram.com/reel/{short_code}/",
            "caption": caption,
            "audio": (i.get("musicInfo") or {}).get("musicName", "Original Audio"),
            "views": views,
            "likes": likes,
            "comments": comments
        })

    filtered.sort(key=lambda x: x["views"], reverse=True)
    return filtered

def generate_prelim_report(data):
    if not data:
        return "No new reels were found from your target profiles in the last week! 🤫"
        
    top_5 = data[:5]
    report = "📊 *Preliminary Analysis: Top 5 Reels (Last 7 Days)*\n\n"
    
    for idx, item in enumerate(top_5, 1):
        report += f"*{idx}.* [Watch Reel]({item['url']})\n"
        report += f"👀 Views: {item['views']} | ❤️ Likes: {item['likes']} | 💬 Comments: {item['comments']}\n"
        cap = item['caption'][:60].replace('\n', ' ') + "..." if item['caption'] else "No caption"
        report += f"📝 _{cap}_\n\n"
        
    report += "🤖 _AI is now analyzing keywords, hashtags, and generating ideas..._"
    return report

def summarize_trends(data):
    if not data:
        return None
        
    prompt = f"""
    Analyze this raw JSON data of Instagram reels from my target creators (posted in the last 7 days).
    The data is already sorted by views:
    {data}
    
    The basic stats (views, likes, top 5) have already been reported. Your job is to dive deeper into the strategy.
    Provide a complete strategic analysis:
    1. 🎵 Best audio tracks/music being used.
    2. 🔑 The most effective keywords and hashtags used by these top performers.
    3. 🧠 Patterns in the captions or video styles (what makes them successful?).
    4. 💡 2-3 concrete, highly-specific ideas for my next reel based on this data.
    
    Format as a punchy, clean Telegram report with emojis. 
    """
    
    free_models = [
        "google/gemma-4-26b-a4b-it:free",
        "nvidia/nemotron-3.5-lightning:free",
        "qwen/qwen3.8-27b:free"
    ]
    
    for model in free_models:
        print(f"Attempting to generate report with {model}...", flush=True)
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=45
            )
            if response.status_code == 200:
                content = response.json().get("choices", [{}])[0].get("message", {}).get("content")
                if content and str(content).strip() and str(content).strip().lower() != "null":
                    return str(content).strip()
                else:
                    print(f"{model} returned null or empty content. Trying next...")
            else:
                print(f"{model} failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"{model} encountered an exception: {e}")
            
    return "⚠️ Failed to generate AI report. All free OpenRouter models hit their rate limits or failed."

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    for chat_id in BROADCAST_CHAT_IDS:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        try:
            res = requests.post(url, json=payload)
            if res.status_code != 200:
                print(f"Failed to send Markdown to {chat_id}: {res.text}. Trying plain text...")
                payload = {"chat_id": chat_id, "text": text}
                res2 = requests.post(url, json=payload)
                if res2.status_code == 200:
                    print(f"Sent plain text message to {chat_id}")
            else:
                print(f"Sent message to {chat_id}")
        except Exception as e:
            print(f"Failed to send to {chat_id}: {e}")

if __name__ == "__main__":
    raw_data = get_instagram_trends()
    
    prelim_msg = generate_prelim_report(raw_data)
    send_telegram_message(prelim_msg)
    
    if raw_data:
        summary = summarize_trends(raw_data)
        if summary:
            send_telegram_message(summary)
