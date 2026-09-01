import os
import sys
import json
import datetime
from dotenv import load_dotenv
from googleapiclient.discovery import build
from src.uploader import get_youtube_service, YOUTUBE_SCOPES
from google import genai
from google.genai import errors
from src.api_manager import gemini_rotator
# Force UTF-8 output so emoji never crash on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Load .env FIRST so secrets are available both locally and in CI
load_dotenv()


HISTORY_FILE = "posted_history.json"
DIRECTIVES_FILE = "ai_directives.txt"

def get_analytics_service(token_file='youtube_token.json'):
    youtube = get_youtube_service(token_file) # Ensure token is valid
    if not youtube: return None
    from google.oauth2.credentials import Credentials
    creds = Credentials.from_authorized_user_file(token_file, YOUTUBE_SCOPES)
    return build('youtubeAnalytics', 'v2', credentials=creds)

def fetch_video_metrics(video_id):
    """Fetches Data API (Views, Likes) and Analytics API (AVD) metrics for a video."""
    youtube = get_youtube_service()
    analytics = get_analytics_service()
    
    metrics = {
        "views": 0,
        "likes": 0,
        "comments": 0,
        "average_view_duration_seconds": "Data Pending (48h delay)"
    }
    
    if not youtube or not analytics:
        return metrics

    # 1. Get Data API Stats (Real-time)
    try:
        res = youtube.videos().list(part="statistics", id=video_id).execute()
        if res.get("items"):
            stats = res["items"][0]["statistics"]
            metrics["views"] = int(stats.get("viewCount", 0))
            metrics["likes"] = int(stats.get("likeCount", 0))
            metrics["comments"] = int(stats.get("commentCount", 0))
    except Exception as e:
        print(f"Error fetching Data API for {video_id}: {e}")

    # 2. Get Analytics API Stats (Delayed)
    try:
        start_date = (datetime.datetime.now() - datetime.timedelta(days=14)).strftime('%Y-%m-%d')
        end_date = datetime.datetime.now().strftime('%Y-%m-%d')
        
        report = analytics.reports().query(
            ids='channel==MINE',
            startDate=start_date,
            endDate=end_date,
            metrics='averageViewDuration',
            dimensions='video',
            filters=f'video=={video_id}'
        ).execute()
        
        if report.get("rows") and len(report["rows"]) > 0:
            # row format: [video_id, averageViewDuration]
            metrics["average_view_duration_seconds"] = round(report["rows"][0][1], 1)
    except Exception as e:
        print(f"Error fetching Analytics API for {video_id}: {e}")

    return metrics

def analyze_and_heal():
    print("🩺 Starting Self-Healing Analytics (The Doctor)...")

    if not os.path.exists(HISTORY_FILE):
        print("   ⚠️ No posted_history.json found. Nothing to analyze.")
        return

    with open(HISTORY_FILE, "r") as f:
        history = json.load(f)

    if not history:
        print("   ⚠️ History is empty.")
        return

    now = datetime.datetime.now()
    min_age_hours = 72   # 3 days  — ensures YouTube Analytics AVD data is available
    max_age_hours = 480  # 20 days — videos older than this have peaked; data is stale

    # Find all videos that are old enough AND have never been analyzed
    pending_videos = []
    skipped_stale = []
    for entry in history:
        if entry.get("analyzed"):
            continue  # already processed, skip
        try:
            post_time = datetime.datetime.fromisoformat(entry["timestamp"])
            age_hours = (now - post_time).total_seconds() / 3600
            if age_hours >= min_age_hours and age_hours <= max_age_hours:
                pending_videos.append(entry)
            elif age_hours > max_age_hours:
                skipped_stale.append(entry)  # too old, auto-expire
        except ValueError:
            pass

    # Auto-mark stale videos as analyzed so they don't accumulate
    if skipped_stale:
        stale_ids = {e["video_id"] for e in skipped_stale}
        for entry in history:
            if entry.get("video_id") in stale_ids:
                entry["analyzed"] = True
                entry["analyzed_note"] = "Auto-expired: older than 20 days"
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
        print(f"   🗑️ Auto-expired {len(skipped_stale)} videos older than 20 days.")

    if not pending_videos:
        print("   ℹ️ No new videos are old enough to analyze yet (need 3+ days for AVD data).")
        print(f"   ⏳ Check back later. All pending videos need to be at least {min_age_hours}h old.")
        return

    print(f"   📊 Found {len(pending_videos)} unanalyzed videos (≥3 days old). Fetching metrics...")

    analysis_payload = []
    analyzed_ids = set()

    for vid in pending_videos:
        metrics = fetch_video_metrics(vid["video_id"])
        # Safely access script_state — it may be a dict or missing entirely
        script_state = vid.get("script_state") or {}
        analysis_payload.append({
            "video_id":   vid["video_id"],
            "posted_on":  vid["timestamp"],
            "script":     script_state.get("quote", ""),
            "hook_style": script_state.get("hook_archetype", "Unknown"),
            "topic":      script_state.get("topic_name", "Unknown"),
            "metrics":    metrics
        })
        analyzed_ids.add(vid["video_id"])
        print(f"      - {vid['video_id']} | Views: {metrics['views']} | AVD: {metrics['average_view_duration_seconds']}s")

    # Build prompt for Gemini
    current_rules = "None (first run)"
    if os.path.exists(DIRECTIVES_FILE):
        with open(DIRECTIVES_FILE, "r") as f:
            current_rules = f.read()

    prompt = f"""
You are the master analyst for a viral psychology YouTube Shorts channel.
Your job is to analyze a batch of videos (all at least 3 days old, with real AVD data) and output new, strict rules to maximize future views and Average View Duration.

CURRENT DIRECTIVES IN PLACE:
{current_rules}

VIDEOS BEING ANALYZED TODAY:
{json.dumps(analysis_payload, indent=2)}

INSTRUCTIONS:
1. Identify which hook styles and topics resulted in the highest views and highest Average View Duration (AVD).
2. Identify what flopped (low views or low retention).
3. Write exactly 3 to 5 new, high-impact rules for the scriptwriter to follow for the NEXT batch of videos.
4. Overwrite the old rules completely. Do NOT output markdown formatting like ```text. Output raw text ONLY.
5. Focus on tangible script changes (e.g., "Hooks must use the 'Fear' archetype because it drove 200% more views").
    """

    print("   🧠 Sending data to Gemini for analysis...")
    
    max_retries = 5
    response = None
    models_to_try = ['gemini-3.7-flash', 'gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3-flash', 'gemini-2.5-flash']
    
    while gemini_rotator.has_keys() and max_retries > 0 and not response:
        max_retries -= 1
        current_key = gemini_rotator.get_random_key()
        client = genai.Client(api_key=current_key)
        
        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                break  # Success, break out of model loop
            except errors.APIError as e:
                print(f"Gemini API Error with model {model_name} on key {current_key[:5]}...: {e}")
                if e.code in [429, 403]:
                    print(f"Key {current_key[:5]}... hit limit. Rotating key...")
                    gemini_rotator.remove_key(current_key)
                    break  # Break out of model loop to try next key
                else:
                    print(f"Falling back to next model...")
                    continue
            except Exception as e:
                print(f"Unexpected error with model {model_name}: {e}")
                continue
            
    if not response:
        print("   ❌ Error: Could not get a response from Gemini. All API keys or models exhausted.")
        return

    new_rules = response.text.strip()

    with open(DIRECTIVES_FILE, "w", encoding="utf-8") as f:
        f.write(new_rules)

    # Mark analyzed videos so they are never processed again
    for entry in history:
        if entry.get("video_id") in analyzed_ids:
            entry["analyzed"] = True

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

    print(f"   ✅ Analysis complete! {len(analyzed_ids)} videos marked as analyzed.")
    print("   💉 New directives saved to ai_directives.txt. The system has healed itself.")

if __name__ == "__main__":
    analyze_and_heal()

