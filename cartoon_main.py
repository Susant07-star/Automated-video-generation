"""
cartoon_main.py — Isolated pipeline for the Cartoon Plus channel.

Run locally:
    python cartoon_main.py

Run in GitHub Actions (headless):
    python cartoon_main.py --headless

This script is COMPLETELY INDEPENDENT from main.py. It uses:
- A separate checkpoint file  (pipeline_state_cartoon.json)
- A separate history file     (generated_history_cartoon.txt)
- A separate YouTube token    (youtube_token_cartoon.json)
- A separate schedule config  (schedule_config_cartoon.json)
- A separate final video file (final_reel_cartoon.mp4)
- The Majnu bhai meme sound   (Majnu bhai funny meme sound.mp4)
"""

import os
import sys
import json
import argparse
from dotenv import load_dotenv

load_dotenv()

from src.content_generator import generate_content
from src.media_fetcher import fetch_background_music, fetch_sequential_local_video
from src.audio_generator import generate_voiceover
from src.video_assembler import assemble_video
from src.uploader import upload_to_youtube

# ─── Cartoon Plus channel-specific constants ─────────────────────────────────
PROFILE           = "cartoon"
CHECKPOINT_FILE   = "pipeline_state_cartoon.json"
FINAL_PATH        = "final_reel_cartoon.mp4"
VOICE_PATH        = "temp_voice_cartoon.mp3"
MUSIC_PATH        = "temp_music_cartoon.mp3"
MEME_SOUND_PATH   = "Majnu bhai funny meme sound.mp4"   # File you added to the repo
YT_TOKEN_FILE     = "youtube_token_cartoon.json"
SCHEDULE_CFG      = "schedule_config_cartoon.json"

# ─── Checkpoint helpers ───────────────────────────────────────────────────────
def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r") as f:
                state = json.load(f)
            print(f"\n🔁 RESUME MODE — Found checkpoint: {CHECKPOINT_FILE}")
            return state
        except Exception:
            pass
    return {}

def save_checkpoint(state: dict):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(state, f, indent=2)

def clear_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

def _file_ready(path):
    return path and os.path.exists(path) and os.path.getsize(path) > 0

# ─── Main pipeline ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Cartoon Plus Automated Reel Generator")
    parser.add_argument("--headless", action="store_true", help="Run without user input (auto-post)")
    args = parser.parse_args()

    print("=" * 60)
    print("  🎭  Cartoon Plus — Funny Hindi Shorts Generator")
    if args.headless:
        print("  🤖  Running in HEADLESS mode (Auto-Posting enabled)")
    print("=" * 60)

    state = load_checkpoint()
    video_paths = []
    success = False

    try:
        # ── STEP 1: Generate funny Hindi content ─────────────────────
        if state.get("content_done"):
            quote     = state["quote"]
            video_kws = state["video_kws"]
            music_kw  = state["music_kw"]
            print(f"\n⏭️  [Step 1/5] Skipping content generation (resumed from checkpoint)")
            print(f"   Script   : {quote[:80]}...")
            print(f"   Video kws: {video_kws}")
        else:
            print("\n▶️  [Step 1/5] Generating funny Hindi script via Gemini...")
            content = generate_content(profile=PROFILE)
            if not content:
                print("❌  Failed to generate content. Exiting.")
                sys.exit(1)

            quote     = content.get("quote", "Yaar, sun ek baat...")
            video_kws = content.get("video_search_keywords", ["soap cutting", "kinetic sand"])
            music_kw  = content.get("music_search_keyword", "funny quirky")
            fomo_overlay = content.get("fomo_overlay", "Wait for it... 🤣")

            yt_title       = content.get("yt_title", "Funny Hindi Short 😂")
            yt_description = content.get("yt_description", "")
            yt_tags        = content.get("yt_tags", ["funny", "hindi", "comedy"])
            fb_caption     = content.get("fb_caption", "")
            fb_hashtags    = content.get("fb_hashtags", "#funny #hindi")

            print(f"   Script   : {quote[:80]}...")
            print(f"   Video kws: {video_kws}")
            print(f"   Music kw : {music_kw}")

            state.update({
                "content_done": True,
                "quote": quote, "video_kws": video_kws, "music_kw": music_kw,
                "fomo_overlay": fomo_overlay,
                "yt_title": yt_title, "yt_description": yt_description, "yt_tags": yt_tags,
                "fb_caption": fb_caption, "fb_hashtags": fb_hashtags,
            })
            save_checkpoint(state)
            print("   ✅ Content saved to checkpoint.")

        # ── STEP 2: Hindi AI Voiceover ────────────────────────────────
        voice_json = VOICE_PATH + ".json"
        if state.get("voice_done") and _file_ready(VOICE_PATH) and _file_ready(voice_json):
            print(f"\n⏭️  [Step 2/5] Skipping voiceover — {VOICE_PATH} already exists")
        else:
            print(f"\n▶️  [Step 2/5] Generating Hindi voiceover...")
            generate_voiceover(quote, VOICE_PATH, profile=PROFILE)
            state["voice_done"] = True
            save_checkpoint(state)
            print("   ✅ Voiceover saved to checkpoint.")

        # ── STEP 3: Background video (Sequential Local) ─────────────────
        video_paths = ["temp_cartoon_bg.mp4"]
        if state.get("video_done") and all(_file_ready(vp) for vp in video_paths):
            print(f"\n⏭️  [Step 3/5] Skipping video extraction — clip already exists")
        else:
            print(f"\n▶️  [Step 3/5] Extracting sequential satisfying background clip...")
            try:
                from moviepy.editor import AudioFileClip
                voice_audio = AudioFileClip(VOICE_PATH)
                voice_dur = voice_audio.duration
                voice_audio.close()
            except Exception as e:
                print(f"Error reading audio duration: {e}. Defaulting to 60s.")
                voice_dur = 60.0
            
            # Add meme sound duration so the video is long enough to cover it naturally
            meme_extra = 0.0
            if os.path.exists(MEME_SOUND_PATH):
                try:
                    from moviepy.editor import AudioFileClip as _A
                    _m = _A(MEME_SOUND_PATH)
                    meme_extra = _m.duration
                    _m.close()
                    print(f"   Meme sound duration: {meme_extra:.1f}s — adding to video fetch.")
                except Exception:
                    pass
            
            target_duration = voice_dur + meme_extra + 2.0  # 2s tail padding
            drive_folder_id = os.getenv("DRIVE_FOLDER_ID")
            fetch_sequential_local_video(target_duration, video_paths[0], drive_folder_id)
            state["video_done"] = True
            save_checkpoint(state)
            print("   ✅ Video saved to checkpoint.")

        # ── STEP 4: Background music ──────────────────────────────────
        if state.get("music_done") and _file_ready(MUSIC_PATH):
            print(f"\n⏭️  [Step 4/5] Skipping music download — {MUSIC_PATH} already exists")
        else:
            print(f"\n▶️  [Step 4/5] Downloading background music ({music_kw})...")
            fetch_background_music(music_kw, MUSIC_PATH)
            state["music_done"] = True
            save_checkpoint(state)
            print("   ✅ Music saved to checkpoint.")

        # ── STEP 5: Assemble video with meme sound ────────────────────
        if state.get("assembly_done") and _file_ready(FINAL_PATH):
            print(f"\n⏭️  [Step 5/5] Skipping assembly — {FINAL_PATH} already exists")
        else:
            print(f"\n▶️  [Step 5/5] Assembling cartoon-style video with meme sound...")
            fomo_overlay = state.get("fomo_overlay", "Wait for it... 🤣")

            meme_path = MEME_SOUND_PATH if os.path.exists(MEME_SOUND_PATH) else None
            if not meme_path:
                print("   ⚠️  Meme sound not found — assembling without it.")

            assemble_video(
                bg_video_paths=video_paths,
                audio_path=VOICE_PATH,
                text=quote,
                output_path=FINAL_PATH,
                bg_music_path=MUSIC_PATH,
                whoosh_path=None,   # No whoosh for cartoon profile
                impact_path=None,   # No impact SFX for cartoon profile
                fomo_overlay=fomo_overlay,
                profile=PROFILE,
                meme_sound_path=meme_path
            )
            state["assembly_done"] = True
            save_checkpoint(state)
            print("   ✅ Assembly saved to checkpoint.")

        # ── STEP 6: Upload to Cartoon Plus YouTube (Private → Scheduled) ─
        print(f"\n▶️  [Step 6/6] Uploading to Cartoon Plus YouTube channel...")

        if args.headless:
            print("   🤖 Headless mode: Automatically proceeding with upload.")
            post_choice = 'y'
        else:
            post_choice = input("Post to Cartoon Plus YouTube? (y/n): ").strip().lower()

        if post_choice == 'y':
            yt_titl = state.get("yt_title", "Funny Hindi Short 😂")
            yt_desc = state.get("yt_description", "")
            yt_tags = state.get("yt_tags", ["funny", "hindi", "comedy"])

            try:
                upload_to_youtube(
                    video_path=FINAL_PATH,
                    title=yt_titl,
                    description=yt_desc,
                    tags=yt_tags,
                    token_file=YT_TOKEN_FILE,           # ← Cartoon Plus channel token
                    schedule_config_file=SCHEDULE_CFG   # ← Cartoon Plus publish schedule
                )
                print("   ✅ Uploaded! Video is PRIVATE and will auto-publish per schedule.")
            except Exception as e:
                print(f"   ❌ YouTube upload failed: {e}")
        else:
            print(f"   🎥 Video saved locally: {FINAL_PATH}")

        success = True

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted. Checkpoint saved. Run again to resume.")
    except Exception as e:
        print(f"\n❌ Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        print(f"   Checkpoint saved to {CHECKPOINT_FILE}. Run again to resume.")
    finally:
        if success:
            print("\n🧹 Cleaning up temporary files...")
            temp_files = video_paths + [MUSIC_PATH, VOICE_PATH, VOICE_PATH + ".json"]
            for f in temp_files:
                if f and os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception:
                        pass
            clear_checkpoint()
            print(f"\n✅ Cartoon Plus pipeline completed! Output: {FINAL_PATH}")
        else:
            print("\n🔒 Temp files kept for resume.")


if __name__ == "__main__":
    main()
