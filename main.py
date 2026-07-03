import os
import sys
from src.content_generator import generate_content
from src.media_fetcher import fetch_background_video, fetch_background_music
from src.audio_generator import generate_voiceover
from src.video_assembler import create_video
from src.uploader import upload_reel

def main():
    print("Starting automated motivational Reel generation...")
    
    # 1. Generate content via Gemini
    content = generate_content()
    if not content:
        print("Failed to generate content. Exiting.")
        sys.exit(1)
        
    quote = content.get("quote", "Success is not final, failure is not fatal: it is the courage to continue that counts.")
    video_kw = content.get("video_search_keyword", "success")
    music_kw = content.get("music_search_keyword", "cinematic")
    caption = content.get("caption", "Keep pushing forward!")
    hashtags = content.get("hashtags", "#motivation #success")
    
    print(f"Generated Quote: {quote}")
    print(f"Video Keyword: {video_kw}")
    print(f"Music Keyword: {music_kw}")
    
    # 2. Fetch Media
    video_path = "temp_bg.mp4"
    music_path = "temp_music.mp3"
    voice_path = "temp_voice.mp3"
    final_video_path = "final_reel.mp4"
    
    try:
        fetch_background_video(video_kw, video_path)
        fetch_background_music(music_kw, music_path)
        
        # 3. Generate AI Voiceover
        generate_voiceover(quote, voice_path)
        
        # 4. Assemble Final Video
        create_video(video_path, voice_path, music_path, quote, final_video_path)
        
        # 5. Upload to Facebook
        print("Preparing to upload to Facebook...")
        if os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN") and os.getenv("FACEBOOK_PAGE_ID") and os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN") != "your_fb_access_token_here":
            upload_reel(final_video_path, caption, hashtags)
        else:
            print("Facebook credentials not fully set up in .env file. Skipping upload. The video is saved locally as final_reel.mp4")
            
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Cleanup temp files
        print("Cleaning up temporary files...")
        for file in [video_path, music_path, voice_path]:
            if os.path.exists(file):
                os.remove(file)
                pass # Optionally leave temp files for debugging if needed
                
    print("Pipeline finished successfully!")

if __name__ == "__main__":
    main()
