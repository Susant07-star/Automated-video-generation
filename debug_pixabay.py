import os
import requests
from dotenv import load_dotenv

load_dotenv()

raw_keys = os.getenv("PIXABAY_API_KEYS", "")
keys = [key.strip() for key in raw_keys.split(",") if key.strip()]

if not keys:
    raise SystemExit("No PIXABAY_API_KEYS found in .env")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

for key in keys:
    print(f"Testing key {key[:5]}...")

    # Test 1: Original audio endpoint WITH user agent
    url1 = f"https://pixabay.com/api/audio/?key={key}&q=cinematic"
    r1 = requests.get(url1, headers=headers, timeout=(10, 30))
    print(f"  Test 1 (/api/audio/): {r1.status_code}")

    # Test 2: Main endpoint with media_type=music
    url2 = f"https://pixabay.com/api/?key={key}&q=cinematic&media_type=music"
    r2 = requests.get(url2, headers=headers, timeout=(10, 30))
    print(f"  Test 2 (/?media_type=music): {r2.status_code}")
    if r2.status_code == 200:
        print("  Test 2 SUCCESS! Keys:", r2.json().keys())
