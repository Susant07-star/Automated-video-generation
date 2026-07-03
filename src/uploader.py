import os
import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")

def upload_reel(video_path: str, caption: str, hashtags: str):
    """
    Uploads a video to a Facebook Page as a Reel using the Graph API.
    """
    if not ACCESS_TOKEN or not PAGE_ID:
        raise ValueError("Facebook credentials (FACEBOOK_PAGE_ACCESS_TOKEN, FACEBOOK_PAGE_ID) are missing.")
        
    full_caption = f"{caption}\n\n{hashtags}"
    
    print("Initializing Reel upload session...")
    
    # 1. Initialize Upload (using v19.0 of Graph API)
    init_url = f"https://graph.facebook.com/v19.0/{PAGE_ID}/video_reels"
    init_payload = {
        "upload_phase": "start",
        "access_token": ACCESS_TOKEN
    }
    
    res = requests.post(init_url, data=init_payload)
    res.raise_for_status()
    init_data = res.json()
    video_id = init_data.get("video_id")
    upload_url = init_data.get("upload_url")
    
    if not video_id or not upload_url:
        raise Exception("Failed to initialize upload session.")
        
    print(f"Uploading video {video_path}...")
    
    # 2. Upload Video Data
    headers = {
        "Authorization": f"OAuth {ACCESS_TOKEN}",
        "offset": "0",
        "file_size": str(os.path.getsize(video_path))
    }
    with open(video_path, 'rb') as f:
        upload_res = requests.post(upload_url, headers=headers, data=f)
    upload_res.raise_for_status()
    
    print("Publishing Reel...")
    
    # 3. Publish Reel
    publish_payload = {
        "upload_phase": "finish",
        "video_id": video_id,
        "video_state": "PUBLISHED",
        "description": full_caption,
        "access_token": ACCESS_TOKEN
    }
    
    pub_res = requests.post(init_url, data=publish_payload)
    pub_res.raise_for_status()
    
    print("Reel published successfully!")
    return pub_res.json()

if __name__ == "__main__":
    # Test upload
    pass
