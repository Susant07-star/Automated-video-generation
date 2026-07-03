import os
import requests
import random
from urllib.parse import quote_plus
from src.api_manager import pexels_rotator, pixabay_rotator

def download_file(url: str, dest_path: str):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, stream=True, headers=headers)
    response.raise_for_status()
    with open(dest_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return dest_path

def fetch_background_video(keyword: str, output_filename="temp_bg.mp4"):
    url = f"https://api.pexels.com/videos/search?query={quote_plus(keyword)}&orientation=portrait&size=large&per_page=15"
    
    while pexels_rotator.has_keys():
        current_key = pexels_rotator.get_random_key()
        headers = {"Authorization": current_key}
        
        response = requests.get(url, headers=headers)
        if response.status_code in [429, 403]:
            print(f"Pexels rate limit hit on key {current_key[:5]}... Rotating...")
            pexels_rotator.remove_key(current_key)
            continue
            
        response.raise_for_status()
        data = response.json()
        
        if not data.get("videos"):
            print(f"No videos found for keyword '{keyword}', falling back to 'nature'.")
            fallback_url = f"https://api.pexels.com/videos/search?query=nature&orientation=portrait&size=large&per_page=15"
            response = requests.get(fallback_url, headers=headers)
            data = response.json()
            
        videos = data.get("videos", [])
        if not videos:
            raise Exception("Could not find any videos on Pexels.")
            
        video = random.choice(videos)
        video_files = sorted(video.get("video_files", []), key=lambda x: x.get('width', 0), reverse=True)
        best_file = video_files[0]
        video_url = best_file['link']
        
        print(f"Downloading video from {video_url}...")
        return download_file(video_url, output_filename)
        
    raise Exception("All Pexels API keys exhausted.")

def fetch_background_music(keyword: str, output_filename="temp_music.mp3"):
    while pixabay_rotator.has_keys():
        current_key = pixabay_rotator.get_random_key()
        url = f"https://pixabay.com/api/audio/?key={current_key}&q={quote_plus(keyword)}"
        
        response = requests.get(url)
        if response.status_code in [429, 403]:
            print(f"Pixabay rate limit hit on key {current_key[:5]}... Rotating...")
            pixabay_rotator.remove_key(current_key)
            continue
            
        response.raise_for_status()
        data = response.json()
        
        hits = data.get("hits", [])
        if not hits:
            print(f"No music found for keyword '{keyword}', falling back to 'cinematic'.")
            fallback_url = f"https://pixabay.com/api/audio/?key={current_key}&q=cinematic"
            response = requests.get(fallback_url)
            data = response.json()
            hits = data.get("hits", [])
            
        if not hits:
            raise Exception("Could not find any music on Pixabay.")
            
        track = random.choice(hits[:10])
        audio_url = track.get("audio", track.get("preview", track.get("audio_download", "")))
        
        if not audio_url:
            raise Exception(f"No audio URL found in track data: {track}")
            
        print(f"Downloading music from {audio_url}...")
        return download_file(audio_url, output_filename)
        
    raise Exception("All Pixabay API keys exhausted.")

if __name__ == "__main__":
    pass
