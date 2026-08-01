import os
import time
import requests
import datetime
import pytz
from dotenv import load_dotenv

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
load_dotenv()

def upload_reel(video_path: str, caption: str, hashtags: str):
    """
    Uploads a video to a Facebook Page as a Reel using the Graph API.
    """
    access_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
    page_id = os.getenv("FACEBOOK_PAGE_ID")

    if not access_token or not page_id or access_token == "your_fb_access_token_here" or page_id == "your_numeric_id_here":
        raise ValueError("Facebook credentials (FACEBOOK_PAGE_ACCESS_TOKEN, FACEBOOK_PAGE_ID) are missing or invalid.")
    full_caption = f"{caption}\n\n{hashtags}"
    
    print("Initializing Reel upload session...")
    
    # 1. Initialize Upload (using v19.0 of Graph API)
    init_url = f"https://graph.facebook.com/v19.0/{page_id}/video_reels"
    init_payload = {
        "upload_phase": "start",
        "access_token": access_token
    }
    
    res = requests.post(init_url, data=init_payload)
    if not res.ok:
        print(f"Facebook Init Error: {res.text}")
    res.raise_for_status()
    init_data = res.json()
    video_id = init_data.get("video_id")
    upload_url = init_data.get("upload_url")
    
    if not video_id or not upload_url:
        raise Exception("Failed to initialize upload session.")
        
    print(f"Uploading video {video_path}...")
    
    # 2. Upload Video Data
    headers = {
        "Authorization": f"OAuth {access_token}",
        "offset": "0",
        "file_size": str(os.path.getsize(video_path))
    }
    with open(video_path, 'rb') as f:
        upload_res = requests.post(upload_url, headers=headers, data=f)
    if not upload_res.ok:
        print(f"Facebook Upload Error: {upload_res.text}")
    upload_res.raise_for_status()
    
    print("Publishing Reel...")
    
    # 3. Publish Reel
    publish_url = f"https://graph.facebook.com/v19.0/{page_id}/video_reels"
    publish_payload = {
        "upload_phase": "finish",
        "video_id": video_id,
        "video_state": "PUBLISHED",
        "description": full_caption,
        "access_token": access_token
    }
    
    pub_res = requests.post(publish_url, data=publish_payload)
    if not pub_res.ok:
        print(f"Facebook Publish Error: {pub_res.text}")
    pub_res.raise_for_status()
    
    print("Reel published successfully!")
    return pub_res.json()

def get_youtube_service():
    creds = None
    if os.path.exists('youtube_token.json'):
        creds = Credentials.from_authorized_user_file('youtube_token.json', YOUTUBE_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('client_secret.json'):
                print("WARNING: client_secret.json not found in root directory.")
                print("Please download it from Google Cloud Console (YouTube Data API v3 -> Credentials -> OAuth 2.0 Client IDs).")
                print("Skipping YouTube upload.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', YOUTUBE_SCOPES)
            creds = flow.run_local_server(port=0)
        with open('youtube_token.json', 'w') as token:
            token.write(creds.to_json())
    return build('youtube', 'v3', credentials=creds)

def get_next_publish_time_iso():
    """
    Returns an ISO 8601 string for the next available slot based on schedule_config.json.
    Strictly uses the configured timezone.
    """
    # Default config
    config_tz = "Asia/Kathmandu"
    publish_times_str = ["12:00", "20:00"]
    
    try:
        if os.path.exists("schedule_config.json"):
            with open("schedule_config.json", "r") as f:
                config = json.load(f)
                config_tz = config.get("timezone", config_tz)
                if "publish_times" in config and isinstance(config["publish_times"], list):
                    if len(config["publish_times"]) > 0:
                        publish_times_str = config["publish_times"]
    except Exception as e:
        print(f"Warning: Could not read schedule_config.json ({e}). Using defaults.")
        
    try:
        tz = pytz.timezone(config_tz)
    except pytz.UnknownTimeZoneError:
        print(f"Warning: Unknown timezone {config_tz}. Defaulting to UTC.")
        tz = pytz.UTC
        
    now = datetime.datetime.now(tz)
    
    # Convert string times "HH:MM" to datetime objects for today in configured TZ
    slots = []
    for t_str in publish_times_str:
        try:
            h, m = map(int, t_str.split(":"))
            slots.append(now.replace(hour=h, minute=m, second=0, microsecond=0))
        except ValueError:
            print(f"Warning: Invalid time format '{t_str}' in schedule_config.json. Expected HH:MM.")
            
    if not slots:
        slots = [now.replace(hour=12, minute=0, second=0, microsecond=0)]
        
    slots.sort()
    
    # Find the next available slot today
    target = None
    for slot in slots:
        if now < slot:
            target = slot
            break
            
    # If no slots left today, pick the first slot of tomorrow
    if target is None:
        target = slots[0] + datetime.timedelta(days=1)
        
    return target.isoformat()

def upload_to_youtube(video_path: str, title: str, description: str, tags: list):
    youtube = get_youtube_service()
    if not youtube:
        return
        
    print(f"Uploading {video_path} to YouTube Shorts...")
    
    # Ensure title is < 100 chars
    title = title[:95] + "..." if len(title) > 95 else title
    
    publish_at_iso = get_next_publish_time_iso()
    print(f"   Scheduling publishAt for: {publish_at_iso}")
    
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "27"  # Education
        },
        "status": {
            "privacyStatus": "private",  # Must be private to use publishAt
            "publishAt": publish_at_iso,
            "selfDeclaredMadeForKids": False
        }
    }
    
    insert_request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True)
    )
    
    response = insert_request.execute()
    video_id = response.get('id')
    print(f"YouTube upload successful! Video ID: {video_id}")
    return response


def upload_to_temporary_host(filepath: str):
    print("Uploading to temporary host (catbox.moe) for Instagram Graph API...")
    with open(filepath, 'rb') as f:
        res = requests.post("https://catbox.moe/user/api.php", data={"reqtype": "fileupload"}, files={"fileToUpload": f})
    res.raise_for_status()
    direct_url = res.text.strip()
    print(f"Temporary URL created: {direct_url}")
    return direct_url

def upload_to_instagram(video_path: str, caption: str, hashtags: str):
    ig_user_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    access_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
    
    if not ig_user_id or ig_user_id == "your_ig_business_id_here":
        print("WARNING: INSTAGRAM_BUSINESS_ACCOUNT_ID missing. Skipping Instagram upload.")
        return
        
    print("Starting Instagram Reels upload process...")
    # 1. Host temporarily
    video_url = upload_to_temporary_host(video_path)
    
    # 2. Create Media Container
    create_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": f"{caption}\n\n{hashtags}",
        "access_token": access_token
    }
    print("Creating Instagram Media Container...")
    res = requests.post(create_url, data=payload)
    if not res.ok:
        print(f"Failed to create IG Media: {res.text}")
        res.raise_for_status()
        
    creation_id = res.json().get("id")
    
    # 3. Wait for processing & Publish
    print("Waiting for Instagram to process video (can take up to 2 mins)...")
    status_url = f"https://graph.facebook.com/v19.0/{creation_id}"
    
    max_retries = 30
    for _ in range(max_retries):
        status_res = requests.get(status_url, params={"fields": "status_code", "access_token": access_token})
        status_data = status_res.json()
        status_code = status_data.get("status_code")
        print(f"IG Processing Status: {status_code}")
        
        if status_code == "FINISHED":
            break
        elif status_code == "ERROR":
            raise Exception("Instagram failed to process the video.")
            
        time.sleep(10)
        
    print("Publishing Instagram Reel...")
    publish_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
    pub_res = requests.post(publish_url, data={"creation_id": creation_id, "access_token": access_token})
    if not pub_res.ok:
        print(f"Failed to publish IG Reel: {pub_res.text}")
        pub_res.raise_for_status()
        
    print("Instagram Reel published successfully!")
    return pub_res.json()

if __name__ == "__main__":
    # Test upload
    pass
