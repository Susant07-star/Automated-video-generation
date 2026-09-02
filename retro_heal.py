import os
import sys
import json
import datetime
from dotenv import load_dotenv
from googleapiclient.discovery import build
from src.uploader import get_youtube_service, YOUTUBE_SCOPES
from google import genai
from google.oauth2.credentials import Credentials
from google.genai import errors
from src.api_manager import gemini_rotator

# Force UTF-8 output so emoji never crash on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()


def get_analytics_service(token_file):
    youtube = get_youtube_service(token_file)
    if not youtube: return None
    if not os.path.exists(token_file):
        return None
    creds = Credentials.from_authorized_user_file(token_file, YOUTUBE_SCOPES)
    return build('youtubeAnalytics', 'v2', credentials=creds)

def fetch_video_metrics(youtube, analytics, video_id):
    """Fetches Data API (Views, Likes) and Analytics API (AVD) metrics for a video."""
    metrics = {
        "views": 0,
        "likes": 0,
        "comments": 0,
        "average_view_duration_seconds": "Data Pending (48h delay)"
    }
    
    if not youtube or not analytics:
        return metrics

    # 1. Get Data API Stats
    try:
        res = youtube.videos().list(part="statistics", id=video_id).execute()
        if res.get("items"):
            stats = res["items"][0]["statistics"]
            metrics["views"] = int(stats.get("viewCount", 0))
            metrics["likes"] = int(stats.get("likeCount", 0))
            metrics["comments"] = int(stats.get("commentCount", 0))
    except Exception as e:
        pass

    # 2. Get Analytics API Stats
    try:
        start_date = (datetime.datetime.now() - datetime.timedelta(days=60)).strftime('%Y-%m-%d')
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
            metrics["average_view_duration_seconds"] = round(report["rows"][0][1], 1)
    except Exception as e:
        pass

    return metrics

def process_channel(channel_name, token_file, directives_file, prompt_template):
    print(f"\n🩺 Starting Retroactive Analytics for [{channel_name}]...")
    
    if not os.path.exists(token_file):
        print(f"   ⚠️ Token file {token_file} not found. Skipping {channel_name}.")
        return

    youtube = get_youtube_service(token_file)
    analytics = get_analytics_service(token_file)

    if not youtube or not analytics:
        print(f"   ❌ Could not authenticate for {channel_name}. Skipping.")
        return

    try:
        print("   🔍 Fetching Uploads playlist...")
        channel_res = youtube.channels().list(mine=True, part="contentDetails").execute()
        if not channel_res.get("items"):
            print("   ❌ Could not find channel details.")
            return
            
        uploads_playlist_id = channel_res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        
        print("   🔍 Fetching recent videos...")
        playlist_res = youtube.playlistItems().list(
            playlistId=uploads_playlist_id,
            part="snippet",
            maxResults=15
        ).execute()
        
        videos = playlist_res.get("items", [])
        if not videos:
            print("   ℹ️ No videos found on this channel.")
            return
            
        print(f"   📊 Found {len(videos)} recent videos. Fetching metrics...")
        
        analysis_payload = []
        for item in videos:
            video_id = item["snippet"]["resourceId"]["videoId"]
            title = item["snippet"]["title"]
            description = item["snippet"]["description"]
            
            metrics = fetch_video_metrics(youtube, analytics, video_id)
            print(f"      - {video_id} | {title[:30]}... | Views: {metrics['views']} | AVD: {metrics['average_view_duration_seconds']}s")
            
            analysis_payload.append({
                "video_id": video_id,
                "title": title,
                "description": description,
                "metrics": metrics
            })
            
        # Load current rules if any
        current_rules = "None (first run)"
        if os.path.exists(directives_file):
            with open(directives_file, "r", encoding="utf-8") as f:
                current_rules = f.read()

        prompt = prompt_template.format(
            current_rules=current_rules,
            payload=json.dumps(analysis_payload, indent=2)
        )

        print(f"   🧠 Sending data to Gemini for {channel_name}...")
        
        max_retries = 5
        response = None
        # Model priority: exhaust ALL keys per model before downgrading.
        # time.sleep(3) after 429s prevents IP-level RPM exhaustion.
        models_to_try = [
            'gemini-3.7-flash',
            'gemini-3.6-flash',
            'gemini-3.5-flash',
            'gemini-3-flash-preview',
            'gemini-2.5-flash',
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
                client = genai.Client(api_key=current_key)
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    print(f"   ✅ Success with model '{model_name}' on key {current_key[:8]}...")
                    break  # Success — break out of key loop
                except errors.APIError as e:
                    print(f"   Gemini API Error — model '{model_name}', key {current_key[:8]}...: {e}")
                    if getattr(e, 'code', None) == 429:
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

        with open(directives_file, "w", encoding="utf-8") as f:
            f.write(new_rules)

        print(f"   ✅ Analysis complete for {channel_name}!")
        print(f"   💉 New directives saved to {directives_file}.")

    except Exception as e:
        print(f"   ❌ Error processing {channel_name}: {e}")

NEXTGEN_PROMPT = """
You are the master analyst for a viral psychology YouTube Shorts channel.
Your job is to analyze a batch of recently posted videos to determine what works and what doesn't. 
Since we only have the video titles, descriptions, and metrics (not the exact original scripts), you must infer the video's topic and hook from its title and description.

CURRENT DIRECTIVES IN PLACE:
{current_rules}

VIDEOS BEING ANALYZED TODAY:
{payload}

INSTRUCTIONS:
1. Identify which topics and title framing resulted in the highest views and highest Average View Duration (AVD).
2. Identify what flopped (low views or low retention).
3. Write exactly 3 to 5 new, high-impact rules for the scriptwriter to follow for the NEXT batch of videos.
4. Overwrite the old rules completely. Do NOT output markdown formatting like ```text. Output raw text ONLY.
5. Focus on tangible script and hook changes inferred from the successful titles (e.g., "Titles/Hooks framed as a 'dark secret' drove 200% more views").
"""

CARTOON_PROMPT = """
You are the chief comedy analyst for 'Cartoon Plus', a Hindi YouTube Shorts channel that pairs calming/ASMR background footage with funny Hindi conversational stories or jokes.
Since we only have the video titles, descriptions, and metrics (not the exact original scripts), you must infer the video's joke topic and hook from its title and description.

CURRENT DIRECTIVES IN PLACE:
{current_rules}

VIDEOS BEING ANALYZED TODAY:
{payload}

INSTRUCTIONS:
1. Identify which joke styles or title topics got the most views and highest AVD.
2. Identify what flopped (low views or low retention).
3. Write exactly 3 to 5 new high-impact rules for the Hindi comedy scriptwriter.
4. Rules must focus on what makes a Cartoon Plus SHORT go viral (funny openers, relatable Hindi dialogue, short punchy punchlines, etc.)
5. Overwrite the old rules completely. Do NOT output markdown formatting like ```text. Output raw text ONLY.
"""

if __name__ == "__main__":
    process_channel("NextGen Thoughts", "youtube_token.json", "ai_directives.txt", NEXTGEN_PROMPT)
    process_channel("Cartoon Plus", "youtube_token_cartoon.json", "ai_directives_cartoon.txt", CARTOON_PROMPT)
    
    print("\n🎉 Retroactive Analysis finished for all channels.")
