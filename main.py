import os
import requests
from apify_client import ApifyClient
from datetime import datetime, timezone, timedelta
import re
from collections import Counter

APIFY_TOKEN = os.environ.get("APIFY_TOKEN")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

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
        hashtags = i.get("hashtags", [])
        
        filtered.append({
            "url": f"https://www.instagram.com/reel/{short_code}/",
            "caption": caption,
            "hashtags": hashtags,
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
        
    return report

def compile_keywords_report(data):
    if not data:
        return None
        
    all_tags = []
    for item in data:
        if item.get("hashtags"):
            all_tags.extend([str(t).lower() for t in item["hashtags"]])
        
        if item.get("caption"):
            extracted = re.findall(r"#(\w+)", item["caption"])
            all_tags.extend([str(t).lower() for t in extracted])
            
    if not all_tags:
        return "No keywords or hashtags found in the recent reels."
        
    tag_counts = Counter(all_tags)
    
    report = "🔑 *Compiled Keywords & Hashtags (Last 7 Days)*\n\n"
    
    for tag, count in tag_counts.most_common(50):
        report += f"#{tag} ({count}x)\n"
        
    return report

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
        kw_msg = compile_keywords_report(raw_data)
        if kw_msg:
            send_telegram_message(kw_msg)
