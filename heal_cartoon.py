"""
heal_cartoon.py — Self-Healing Analytics Doctor for the Cartoon Plus channel.

This is the CARTOON PLUS equivalent of heal.py.
It analyzes the last 7 days of Cartoon Plus videos and generates new directives
saved to ai_directives_cartoon.txt to improve future scripts.

Run manually:
    python heal_cartoon.py

Or triggered automatically by scheduler_cartoon.py on your chosen Analytics Day.
"""

import os
import sys
import json
import datetime
import time
from googleapiclient.discovery import build
from src.uploader import get_youtube_service, YOUTUBE_SCOPES
from google.genai import errors
from src.api_manager import create_gemini_client, gemini_rotator, is_gemini_model_overloaded, is_gemini_timeout
from dotenv import load_dotenv

# Force UTF-8 output so emoji never crash on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()


# Cartoon Plus specific files
HISTORY_FILE   = "posted_history_cartoon.json"
DIRECTIVES_FILE = "ai_directives_cartoon.txt"
TOKEN_FILE     = "youtube_token_cartoon.json"

def get_analytics_service(token_file=TOKEN_FILE):
    youtube = get_youtube_service(token_file=token_file)
    if not youtube:
        return None
    from google.oauth2.credentials import Credentials
    creds = Credentials.from_authorized_user_file(token_file, YOUTUBE_SCOPES)
    return build('youtubeAnalytics', 'v2', credentials=creds)

def fetch_video_metrics(video_id):
    """Fetches Data API (Views, Likes) and Analytics API (AVD) metrics for a video."""
    youtube = get_youtube_service(token_file=TOKEN_FILE)
    analytics = get_analytics_service(token_file=TOKEN_FILE)

    metrics = {
        "views": 0,
        "likes": 0,
        "comments": 0,
        "average_view_duration_seconds": "Data Pending (48h delay)"
    }

    if not youtube or not analytics:
        return metrics

    # 1. Data API (Real-time)
    try:
        res = youtube.videos().list(part="statistics", id=video_id).execute()
        if res.get("items"):
            stats = res["items"][0]["statistics"]
            metrics["views"]    = int(stats.get("viewCount", 0))
            metrics["likes"]    = int(stats.get("likeCount", 0))
            metrics["comments"] = int(stats.get("commentCount", 0))
    except Exception as e:
        print(f"   ⚠️  Data API error for {video_id}: {e}")

    # 2. Analytics API (48h delay)
    try:
        start_date = (datetime.datetime.now() - datetime.timedelta(days=14)).strftime('%Y-%m-%d')
        end_date   = datetime.datetime.now().strftime('%Y-%m-%d')

        report = analytics.reports().query(
            ids='channel==MINE',
            startDate=start_date,
            endDate=end_date,
            metrics='averageViewDuration',
            dimensions='video',
            filters=f'video=={video_id}'
        ).execute()

        if report.get("rows"):
            metrics["average_view_duration_seconds"] = round(report["rows"][0][1], 1)
    except Exception as e:
        print(f"   ⚠️  Analytics API error for {video_id}: {e}")

    return metrics

def analyze_and_heal():
    print("🩺 [Cartoon Plus] Starting Self-Healing Analytics (The Doctor)...")

    if not os.path.exists(HISTORY_FILE):
        print("   ⚠️ No posted_history_cartoon.json found. Nothing to analyze yet.")
        return

    with open(HISTORY_FILE, "r") as f:
        history = json.load(f)

    if not history:
        print("   ⚠️ Cartoon Plus history is empty.")
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
        print("   ℹ️ No new Cartoon Plus videos are old enough to analyze yet (need 3+ days for AVD data).")
        print(f"   ⏳ Check back later. All pending videos need to be at least {min_age_hours}h old.")
        return

    print(f"   📊 Found {len(pending_videos)} unanalyzed videos (≥3 days old). Fetching metrics...")

    analysis_payload = []
    analyzed_ids = set()

    for vid in pending_videos:
        metrics = fetch_video_metrics(vid["video_id"])
        analysis_payload.append({
            "video_id":  vid["video_id"],
            "posted_on": vid["timestamp"],
            "script":    vid["script_state"].get("quote", ""),
            "topic":     vid["script_state"].get("topic_name", "Unknown"),
            "metrics":   metrics
        })
        analyzed_ids.add(vid["video_id"])
        print(f"      - {vid['video_id']} | Views: {metrics['views']} | AVD: {metrics['average_view_duration_seconds']}s")

    # Load current cartoon rules
    current_rules = "None (first run)"
    if os.path.exists(DIRECTIVES_FILE):
        with open(DIRECTIVES_FILE, "r", encoding="utf-8") as f:
            current_rules = f.read()

    prompt = f"""
You are the chief comedy analyst for 'Cartoon Plus', a Hindi YouTube Shorts channel that pairs
calming/ASMR background footage with funny Hindi conversational stories or jokes.

Your job is to analyze a batch of videos (all at least 3 days old, with real AVD data) and generate new rules
to maximize views and Average View Duration.

CURRENT DIRECTIVES IN PLACE:
{current_rules}

VIDEOS BEING ANALYZED TODAY:
{json.dumps(analysis_payload, indent=2)}

INSTRUCTIONS:
1. Identify which joke styles, topics, or story formats got the most views and highest AVD.
2. Identify what flopped (low views or low retention).
3. Write exactly 3 to 5 new high-impact rules for the Hindi comedy scriptwriter.
4. Rules must focus on what makes a Cartoon Plus SHORT go viral (funny openers, relatable Hindi dialogue, short punchy punchlines, etc.)
5. Overwrite the old rules completely. Do NOT output markdown. Output raw text ONLY.
    """

    print("   🧠 Sending Cartoon Plus data to Gemini for analysis...")
    
    max_retries = 5
    response = None
    # Model priority: rotate keys for key/quota errors, but skip a model
    # quickly on 503/504 backend errors or timeout because keys cannot fix overload.
    models_to_try = [
        item.strip()
        for item in os.getenv(
            "GEMINI_CARTOON_HEAL_MODELS",
            "gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash,gemini-3-flash-preview,gemini-2.5-flash",
        ).split(",")
        if item.strip()
    ]
    
    for model_name in models_to_try:
        if response:
            break
        keys_to_try = gemini_rotator.get_all_keys()
        print(f"   🤖 Trying model '{model_name}' across {len(keys_to_try)} key(s)...")
        skip_model = False
        for current_key in keys_to_try:
            if not gemini_rotator.has_keys():
                break
            client = create_gemini_client(current_key)
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                print(f"   ✅ Success with model '{model_name}' on key {current_key[:8]}...")
                break  # Success — break out of key loop
            except errors.APIError as e:
                print(f"   Gemini API Error — model '{model_name}', key {current_key[:8]}...: {e}")
                code = getattr(e, 'code', None)
                if is_gemini_model_overloaded(e):
                    print(f"   ↳ 503/504 backend timeout or high demand on '{model_name}'. Skipping this model tier instead of trying more keys...")
                    skip_model = True
                    break
                if code == 429:
                    error_str = str(e).lower()
                    if "quota" in error_str or "exhausted" in error_str:
                        print(f"   ↳ 429 Quota exhausted for this model. Moving to next key...")
                    else:
                        print(f"   ↳ 429 rate limit. Sleeping 3s, then trying next key...")
                        time.sleep(3)
                    continue        # Try next key with same model
                elif getattr(e, 'code', None) == 403:
                    print(f"   ↳ 403 Forbidden. Removing key globally...")
                    gemini_rotator.remove_key(current_key)
                    continue
                elif getattr(e, 'code', None) in (404, 400):
                    print(f"   ↳ Model error ({getattr(e, 'code', None)}). Moving to next model tier...")
                    skip_model = True
                    break           # Exit key loop, flag to skip model
                else:
                    print(f"   ↳ Other API error ({getattr(e, 'code', None)}). Moving to next key...")
                    continue
            except Exception as e:
                if is_gemini_timeout(e):
                    print(f"   ↳ Gemini request timed out on '{model_name}'. Skipping this model tier...")
                    skip_model = True
                    break
                print(f"   Unexpected error with model '{model_name}': {e}")
                continue
        if response or skip_model:
            continue
        if not response:
            print(f"   ⚠️  Model '{model_name}' exhausted across all keys. Falling back...")
            
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

    print(f"   ✅ Analysis complete! {len(analyzed_ids)} Cartoon Plus videos marked as analyzed.")
    print("   💉 New directives saved to ai_directives_cartoon.txt. Cartoon Plus has healed itself.")

if __name__ == "__main__":
    analyze_and_heal()
