import os
import requests
from dotenv import load_dotenv

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
    upload_res.raise_for_status()
    
    print("Publishing Reel...")
    
    # 3. Publish Reel
    publish_payload = {
        "upload_phase": "finish",
        "video_id": video_id,
        "video_state": "PUBLISHED",
        "description": full_caption,
        "access_token": access_token
    }
    
    pub_res = requests.post(init_url, data=publish_payload)
    pub_res.raise_for_status()
    
    print("Reel published successfully!")
    return pub_res.json()

if __name__ == "__main__":
    # Test upload
    pass
