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
    print("🚀 Scheduler thread started. Reading config dynamically every cycle.")
    last_config_log = None
    
    while True:
        # Re-read config every loop so dashboard changes apply without redeployment
        config = load_config()
        tz_name = config.get("timezone", "Asia/Kathmandu")
        generation_times = config.get("generation_times", ["08:00", "18:45"])
        
        # Log config once whenever it changes
        config_key = str(generation_times)
        if config_key != last_config_log:
            print(f"\n🔄 Config loaded. Timezone: {tz_name}")
            print(f"   🎬 Generation Times (NPT): {generation_times}")
            print(f"   📺 Publish Times (NPT): {config.get('publish_times', ['12:00', '20:00'])}")
            last_config_log = config_key
        
        now = get_current_time_in_tz(tz_name)
        current_time_str = now.strftime("%H:%M")
        
        # Check if the current minute matches a generation time
        # Only trigger in the first 10 seconds of that minute to avoid double-trigger
        if current_time_str in generation_times and now.second < 10:
            print(f"\n⏰ Time matched ({current_time_str} {tz_name})! Starting generation job...")
            run_video_generation()
            # Sleep 65s so we don't trigger again in the same minute
            time.sleep(65)
            continue
            
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
