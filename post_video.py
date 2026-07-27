import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

from src.uploader import upload_reel, upload_to_youtube, upload_to_instagram

def main():
    print("=" * 60)
    print("  🚀  Manual Video Uploader")
    print("=" * 60)

    final_path = "final_reel.mp4"
    metadata_path = "final_reel_metadata.json"

    if not os.path.exists(final_path):
        print(f"❌ Error: {final_path} not found. Run main.py first.")
        sys.exit(1)
        
    if not os.path.exists(metadata_path):
        # Fallback to pipeline_state.json if metadata wasn't saved separately
        if os.path.exists("pipeline_state.json"):
            metadata_path = "pipeline_state.json"
        else:
            print(f"❌ Error: {metadata_path} not found. No SEO data available.")
            sys.exit(1)

    with open(metadata_path, "r") as f:
        state = json.load(f)

    print("✅ Loaded video and SEO metadata.")
    
    # Extract SEO data (with fallbacks for older checkpoints)
    generic_cap = state.get("caption", "")
    generic_hash = state.get("hashtags", "")
    
    fb_cap = state.get("fb_caption", generic_cap)
    fb_hash = state.get("fb_hashtags", generic_hash)
    yt_titl = state.get("yt_title", generic_cap.split('\n')[0] if generic_cap else "Short")
    yt_desc = state.get("yt_description", f"{generic_cap}\n{generic_hash}")
    yt_tags = state.get("yt_tags", [t.strip('#') for t in generic_hash.split()])
    ig_cap = state.get("ig_caption", generic_cap)
    ig_hash = state.get("ig_hashtags", generic_hash)

    print("\n▶️  Uploading to Facebook...")
    fb_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
    fb_page  = os.getenv("FACEBOOK_PAGE_ID", "")
    if fb_token and fb_page and fb_token != "your_fb_access_token_here":
        try:
            upload_reel(final_path, fb_cap, fb_hash)
        except Exception as e:
            print(f"   ❌ Facebook upload failed: {e}")
    else:
        print("   ⚠️ Facebook credentials not set. Skipping.")
        
    print("\n▶️  Uploading to YouTube...")
    try:
        upload_to_youtube(final_path, yt_titl, yt_desc, yt_tags)
    except Exception as e:
        print(f"   ❌ YouTube upload failed: {e}")
        
    print("\n▶️  Uploading to Instagram...")
    ig_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
    if ig_id and ig_id != "your_ig_business_id_here":
        try:
            upload_to_instagram(final_path, ig_cap, ig_hash)
        except Exception as e:
            print(f"   ❌ Instagram upload failed: {e}")
    else:
        print("   ⚠️ Instagram credentials not set. Skipping.")

    print("\n🎉 Upload process completed!")

if __name__ == "__main__":
    main()
