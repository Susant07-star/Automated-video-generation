import os
import json
import time
import pytz
import schedule
import subprocess
from datetime import datetime
from threading import Thread
from flask import Flask

# --- Configuration ---
CONFIG_FILE = "schedule_config.json"
app = Flask(__name__)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {
            "timezone": "Asia/Kathmandu",
            "generation_times": ["08:00", "18:45"],
            "publish_times": ["12:00", "20:00"]
        }
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def run_video_generation():
    print(f"\n[{datetime.now()}] 🚀 Triggering video generation pipeline...")
    try:
        # Run main.py as a subprocess with headless flag
        subprocess.run(["python", "main.py", "--headless"], check=True)
        print(f"[{datetime.now()}] ✅ Video generation completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"[{datetime.now()}] ❌ Video generation failed: {e}")

def get_current_time_in_tz(tz_name):
    try:
        tz = pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        print(f"Warning: Unknown timezone {tz_name}. Defaulting to UTC.")
        tz = pytz.UTC
    return datetime.now(tz)

def start_scheduler():
    config = load_config()
    tz_name = config.get("timezone", "Asia/Kathmandu")
    generation_times = config.get("generation_times", ["08:00", "18:45"])
    
    print(f"🕒 Scheduler started. Timezone: {tz_name}")
    print(f"🎥 Scheduled Generation Times: {generation_times}")
    print(f"📺 Scheduled Publish Times: {config.get('publish_times', ['12:00', '20:00'])}")
    
    # We can't easily use the `schedule` library with strict timezones out-of-the-box 
    # without doing custom math, so we'll just implement a simple timezone-aware loop.
    
    while True:
        now = get_current_time_in_tz(tz_name)
        current_time_str = now.strftime("%H:%M")
        
        # Check if the current minute matches a generation time
        # We only want to trigger it once during that minute.
        if current_time_str in generation_times and now.second < 10:
            print(f"⏰ Time matched ({current_time_str})! Starting generation job...")
            run_video_generation()
            # Sleep for 60 seconds to avoid triggering again in the same minute
            time.sleep(60)
            
        # Sleep for a few seconds before checking again
        time.sleep(5)

# --- Render Dummy Web Server ---
@app.route("/")
def health_check():
    config = load_config()
    tz = pytz.timezone(config.get("timezone", "UTC"))
    return f"Status: OK. Current Time: {datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S %Z')}"

def start_web_server():
    # Render assigns a port via the PORT environment variable
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Start the scheduler in a background thread
    scheduler_thread = Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Start the Flask web server on the main thread
    start_web_server()
