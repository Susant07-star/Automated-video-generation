import os
import sys
import json
from dotenv import load_dotenv

# Ensure environment variables are loaded FIRST
load_dotenv()

from src.content_generator import generate_content
from src.media_fetcher import fetch_background_video, fetch_background_music
from src.audio_generator import generate_voiceover
from src.video_assembler import assemble_video
from src.uploader import upload_reel

CHECKPOINT_FILE = "pipeline_state.json"

# ─────────────────────────────────────────────────────────────
# Checkpoint helpers
# ─────────────────────────────────────────────────────────────

def load_checkpoint():
    """Load saved pipeline state from disk, or return an empty dict."""
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
    """Persist current pipeline state to disk."""
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(state, f, indent=2)


def clear_checkpoint():
    """Delete the checkpoint file after a fully successful run."""
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)


def _file_ready(path):
    """Return True if the file exists and is non-empty."""
    return path and os.path.exists(path) and os.path.getsize(path) > 0


# ─────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  🎬  Automated Motivational Reel Generator")
    print("=" * 60)

    state = load_checkpoint()

    video_path    = "temp_bg.mp4"
    music_path    = "temp_music.mp3"
    voice_path    = "temp_voice.mp3"
    final_path    = "final_reel.mp4"

    success = False

    try:
        # ── STEP 1: Generate content ─────────────────────────────
        if state.get("content_done"):
            quote    = state["quote"]
            video_kw = state["video_kw"]
            music_kw = state["music_kw"]
            caption  = state["caption"]
            hashtags = state["hashtags"]
            print(f"\n⏭️  [Step 1/5] Skipping content generation (resumed from checkpoint)")
            print(f"   Quote    : {quote}")
            print(f"   Video kw : {video_kw}")
            print(f"   Music kw : {music_kw}")
        else:
            print("\n▶️  [Step 1/5] Generating content via Gemini...")
            content = generate_content()
            if not content:
                print("❌  Failed to generate content. Exiting.")
                sys.exit(1)

            quote    = content.get("quote", "Success is not final, failure is not fatal.")
            video_kw = content.get("video_search_keyword", "success")
            music_kw = content.get("music_search_keyword", "cinematic")
            caption  = content.get("caption", "Keep pushing forward!")
            hashtags = content.get("hashtags", "#motivation #success")

            print(f"   Quote    : {quote}")
            print(f"   Video kw : {video_kw}")
            print(f"   Music kw : {music_kw}")

            state.update({
                "content_done": True,
                "quote": quote, "video_kw": video_kw, "music_kw": music_kw,
                "caption": caption, "hashtags": hashtags,
            })
            save_checkpoint(state)
            print("   ✅ Content saved to checkpoint.")

        # ── STEP 2: Background video ──────────────────────────────
        if state.get("video_done") and _file_ready(video_path):
            print(f"\n⏭️  [Step 2/5] Skipping video download — {video_path} already exists")
        else:
            print(f"\n▶️  [Step 2/5] Downloading background video...")
            fetch_background_video(video_kw, video_path)
            state["video_done"] = True
            save_checkpoint(state)
            print("   ✅ Video saved to checkpoint.")

        # ── STEP 3: Background music ──────────────────────────────
        if state.get("music_done") and _file_ready(music_path):
            print(f"\n⏭️  [Step 3/5] Skipping music download — {music_path} already exists")
        else:
            print(f"\n▶️  [Step 3/5] Downloading background music...")
            fetch_background_music(music_kw, music_path)
            state["music_done"] = True
            save_checkpoint(state)
            print("   ✅ Music saved to checkpoint.")

        # ── STEP 4: AI Voiceover ──────────────────────────────────
        voice_json = voice_path + ".json"
        if state.get("voice_done") and _file_ready(voice_path) and _file_ready(voice_json):
            print(f"\n⏭️  [Step 4/5] Skipping voiceover — {voice_path} already exists")
        else:
            print(f"\n▶️  [Step 4/5] Generating ElevenLabs voiceover (Adam)...")
            generate_voiceover(quote, voice_path)
            state["voice_done"] = True
            save_checkpoint(state)
            print("   ✅ Voiceover saved to checkpoint.")

        # ── STEP 5: Assemble video ────────────────────────────────
        if state.get("assembly_done") and _file_ready(final_path):
            print(f"\n⏭️  [Step 5/5] Skipping assembly — {final_path} already exists")
        else:
            print(f"\n▶️  [Step 5/5] Assembling cinematic video...")
            print(f"   This step cannot be partially resumed — rendering from frame 0.")
            print(f"   (All media is already local, so this is the only long step)\n")
            assemble_video(video_path, voice_path, quote, final_path, music_path)
            state["assembly_done"] = True
            save_checkpoint(state)
            print("   ✅ Assembly saved to checkpoint.")

        # ── STEP 6 (optional): Upload to Facebook ─────────────────
        fb_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
        fb_page  = os.getenv("FACEBOOK_PAGE_ID", "")
        print(f"\n▶️  [Step 6/5] Facebook upload...")
        if fb_token and fb_page and fb_token != "your_fb_access_token_here":
            upload_reel(final_path, caption, hashtags)
        else:
            print("   ⚠️  Facebook credentials not set. Skipping upload.")
            print(f"   🎥 Video saved locally: {final_path}")

        success = True

    except KeyboardInterrupt:
        print("\n\n⚠️  Run interrupted by user (Ctrl+C).")
        print(f"   Checkpoint saved to {CHECKPOINT_FILE}")
        print("   Run 'python main.py' again to resume from this point.")
    except Exception as e:
        print(f"\n❌ Pipeline error: {e}")
        print(f"   Checkpoint saved to {CHECKPOINT_FILE}")
        print("   Run 'python main.py' again to resume.")
    finally:
        if success:
            # Full success — clean up ALL temp files and checkpoint
            print("\n🧹 Cleaning up temporary files...")
            for f in [video_path, music_path, voice_path, voice_path + ".json"]:
                if f and os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception:
                        pass
            clear_checkpoint()
            print(f"\n✅ Pipeline completed successfully! Output: {final_path}")
        else:
            # Partial failure — keep temp files + checkpoint for next run
            print("\n🔒 Temp files KEPT for resume. Do NOT delete them manually.")
            print(f"   temp_bg.mp4       : Background video")
            print(f"   temp_music.mp3    : Background music")
            print(f"   temp_voice.mp3    : Voiceover audio")
            print(f"   pipeline_state.json: Checkpoint (resume marker)")


if __name__ == "__main__":
    main()
