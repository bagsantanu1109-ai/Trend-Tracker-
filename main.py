import os
import requests
from apify_client import ApifyClient
from datetime import datetime, timezone, timedelta

APIFY_TOKEN = os.environ.get("APIFY_TOKEN")
# Read the OpenRouter key (if the user updated GEMINI_API_KEY secret, fallback to that)
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

ENV_CHAT_IDS = [x.strip() for x in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if x.strip()]
BROADCAST_CHAT_IDS = set(ENV_CHAT_IDS + ["8300734497", "1326228475"])

import random
import re

def get_instagram_trends():
    client = ApifyClient(APIFY_TOKEN)
    
    # Load tags
    try:
        with open("bangali_creators.txt", "r") as f:
            all_tags = [line.strip() for line in f if line.strip()]
    except Exception:
        all_tags = ["kolkata", "bengali", "calcutta"]
        
    selected_tags = random.sample(all_tags, min(5, len(all_tags)))
    direct_urls = [f"https://www.instagram.com/explore/tags/{t}/" for t in selected_tags]
    print(f"Scraping tags: {selected_tags}")

    run_input = {
        "directUrls": direct_urls,
        "resultsLimit": 50, # 50 per tag = 250 total, fast and cheap
    }
    run = client.actor("apify/instagram-scraper").call(run_input=run_input)
    dataset_id = run["defaultDatasetId"] if isinstance(run, dict) else run.default_dataset_id
    items = list(client.dataset(dataset_id).iterate_items())
    
    filtered = []
    now = datetime.now(timezone.utc)
    new_learned_tags = set()
    
    for i in items:
        # Filter strictly for video/reels
        if i.get("productType") != "clips" and not i.get("isVideo"):
            continue
            
        # Filter for recent 24 hours
        ts_str = i.get("timestamp")
        if ts_str:
            try:
                dt = datetime.strptime(ts_str.split(".")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                if now - dt > timedelta(hours=24):
                    continue
            except Exception:
                pass
                
        # Filter out celebs
        owner = i.get("owner", {})
        if owner.get("is_verified") or owner.get("followersCount", 0) > 1000000:
            continue
            
        views = i.get("videoViewCount") or i.get("playCount") or i.get("viewCount") or 0
        if views == 0 or views == -1:
            continue
            
        short_code = i.get("shortCode") or i.get("url", "").rstrip("/").split("/")[-1]
        caption = i.get("caption", "")
        
        filtered.append({
            "url": f"https://www.instagram.com/reel/{short_code}/",
            "caption": caption,
            "audio": (i.get("musicInfo") or {}).get("musicName", "Original Audio"),
            "views": views
        })
        
        # Self-learning hashtags
        found_tags = i.get("hashtags", [])
        if not found_tags:
            found_tags = re.findall(r"#(\w+)", caption)
            
        for tag in found_tags:
            tag_lower = tag.lower()
            # Only learn strictly relevant local tags
            if any(k in tag_lower for k in ["kolkata", "bengali", "calcutta", "howrah", "bong"]):
                if tag_lower not in all_tags:
                    new_learned_tags.add(tag_lower)
                    
    # Save newly learned tags
    if new_learned_tags:
        print(f"Learned {len(new_learned_tags)} new tags! Adding to bangali_creators.txt")
        all_tags.extend(list(new_learned_tags))
        # Deduplicate and sort
        all_tags = sorted(list(set(all_tags)))
        with open("bangali_creators.txt", "w") as f:
            for tag in all_tags:
                f.write(f"{tag}\n")
                
    return filtered

def summarize_trends(data):
    if not data:
        return "No new non-celeb Indian Instagram trends found in the last 24 hours! 🤫"
        
    prompt = f"""
    Analyze this raw JSON data of Instagram reels from Kolkata creators (last 24 hours): 
    {data}
    
    Provide a complete analysis for my next reel:
    1. 🏆 Top 5 reels with the most views (include a tiny summary of their caption).
    2. 🎵 5 most used songs/audio tracks.
    3. 🔑 All the best keywords/hashtags for good visibility.
    4. 🧠 Complete analysis and patterns observed (what is working right now?).
    5. 💡 A solid, concrete idea for my next reel based on these trends.
    
    Format as a punchy, clean Telegram report with emojis. Keep it readable.
    """
    
    # List of free OpenRouter models to cycle through
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
                return response.json()["choices"][0]["message"]["content"]
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
