import os
import sys
import json
import argparse
import datetime
from dotenv import load_dotenv

# Force UTF-8 output so emoji in print() never crash on Windows cp1252 terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Ensure environment variables are loaded FIRST
load_dotenv()

from src.content_generator import generate_content
from src.media_fetcher import fetch_background_video, fetch_background_music, fetch_whoosh_sfx, fetch_impact_sfx
from src.audio_generator import generate_voiceover
from src.video_assembler import assemble_video
from src.uploader import upload_reel, upload_to_youtube, upload_to_instagram

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
    parser = argparse.ArgumentParser(description="Automated Motivational Reel Generator")
    parser.add_argument("--headless", action="store_true", help="Run without user input (auto-post)")
    args = parser.parse_args()

    print("=" * 60)
    print("  🎬  Automated Motivational Reel Generator")
    if args.headless:
        print("  🤖  Running in HEADLESS mode (Auto-Posting enabled)")
    print("=" * 60)

    state = load_checkpoint()

    video_paths   = []  # Populated dynamically after content generation
    music_path    = "temp_music.mp3"
    voice_path    = "temp_voice.mp3"
    whoosh_path   = "temp_whoosh.mp3"
    impact_path   = "temp_impact.wav"
    final_path    = "final_reel.mp4"

    success = False

    try:
        # ── STEP 1: Generate content ─────────────────────────────
        if state.get("content_done"):
            quote    = state["quote"]
            video_kws = state["video_kws"]
            music_kw = state["music_kw"]
            print(f"\n⏭️  [Step 1/5] Skipping content generation (resumed from checkpoint)")
            print(f"   Quote    : {quote}")
            print(f"   Video kws: {video_kws}")
            print(f"   Music kw : {music_kw}")
        else:
            print("\n▶️  [Step 1/5] Generating content via Gemini...")
            content = generate_content()
            if not content:
                print("❌  Failed to generate content. Exiting.")
                sys.exit(1)

            quote    = content.get("quote", "Success is not final, failure is not fatal.")
            topic_name = content.get("topic_name", "Unknown")
            video_kws = content.get("video_search_keywords", ["success", "motivation", "grind"])
            music_kw = content.get("music_search_keyword", "cinematic")
            
            # Backwards compatibility for generic caption/hashtags
            generic_caption = content.get("caption", "Keep pushing forward!")
            generic_hashtags = content.get("hashtags", "#motivation")
            
            fomo_overlay = content.get("fomo_overlay", "Wait for the end...")
            hook_archetype = content.get("hook_archetype", "Unknown")
            creative_angle = content.get("creative_angle", "")
            audience_pain = content.get("audience_pain", "")
            retention_beats = content.get("retention_beats", [])
            research_brief_file = content.get("research_brief_file", "")
            research_brief = content.get("research_brief", {})
            
            yt_title = content.get("yt_title", generic_caption.split('\n')[0])
            yt_description = content.get("yt_description", f"{generic_caption}\n\n{generic_hashtags}")
            yt_tags = content.get("yt_tags", [t.strip('#') for t in generic_hashtags.split()])
            
            fb_caption = content.get("fb_caption", generic_caption)
            fb_hashtags = content.get("fb_hashtags", generic_hashtags)
            
            ig_caption = content.get("ig_caption", generic_caption)
            ig_hashtags = content.get("ig_hashtags", generic_hashtags)

            print(f"   Quote    : {quote}")
            if creative_angle:
                print(f"   Angle    : {creative_angle}")
            print(f"   Video kws: {video_kws}")
            print(f"   Music kw : {music_kw}")

            state.update({
                "content_done": True,
                "topic_name": topic_name,
                "quote": quote, "video_kws": video_kws, "music_kw": music_kw,
                "fomo_overlay": fomo_overlay,
                "hook_archetype": hook_archetype,
                "creative_angle": creative_angle,
                "audience_pain": audience_pain,
                "retention_beats": retention_beats,
                "research_brief_file": research_brief_file,
                "research_brief": research_brief,
                "yt_title": yt_title, "yt_description": yt_description, "yt_tags": yt_tags,
                "fb_caption": fb_caption, "fb_hashtags": fb_hashtags,
                "ig_caption": ig_caption, "ig_hashtags": ig_hashtags
            })
            save_checkpoint(state)
            print("   ✅ Content saved to checkpoint.")

        # Dynamically set video paths based on how many keywords were generated
        video_paths = [f"temp_bg_{i+1}.mp4" for i in range(len(video_kws))]

        # ── STEP 2: Background video & SFX ────────────────────────
        if state.get("video_done") and all(_file_ready(vp) for vp in video_paths) and _file_ready(whoosh_path) and _file_ready(impact_path):
            print(f"\n⏭️  [Step 2/5] Skipping video download — background clips already exist")
        else:
            print(f"\n▶️  [Step 2/5] Downloading {len(video_kws)} background clips and SFX...")
            fetch_background_video(video_kws, video_paths)
            fetch_whoosh_sfx(whoosh_path)
            fetch_impact_sfx(impact_path)
            state["video_done"] = True
            save_checkpoint(state)
            print("   ✅ Video and SFX saved to checkpoint.")

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
            # Reconstruct thumbnail path in case we are resuming
            thumb_path = state.get("thumbnail_path", final_path.replace(".mp4", "_thumbnail.jpg"))
        else:
            print(f"\n▶️  [Step 5/5] Assembling cinematic multi-clip video...")
            print(f"   This step cannot be partially resumed — rendering from frame 0.")
            print(f"   (All media is already local, so this is the only long step)\n")
            
            fomo_overlay = state.get("fomo_overlay", "Wait for the end...")
            thumb_path = assemble_video(video_paths, voice_path, quote, final_path, music_path, whoosh_path, impact_path, fomo_overlay=fomo_overlay) or ""
            
            state["assembly_done"] = True
            state["thumbnail_path"] = thumb_path
            save_checkpoint(state)
            print("   ✅ Assembly saved to checkpoint.")

        # ── STEP 6: Omnichannel Upload ────────────────────────────
        print(f"\n▶️  [Step 6/6] Omnichannel Upload...")
        
        if args.headless:
            print("   🤖 Headless mode: Automatically proceeding with uploads.")
            post_choice = 'y'
        else:
            post_choice = input("Do you want to post this video to your platforms? (y/n): ").strip().lower()
            
        if post_choice == 'y':
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
            
            # Facebook
            thumb_path = state.get("thumbnail_path", "")
            fb_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
            fb_page  = os.getenv("FACEBOOK_PAGE_ID", "")
            if fb_token and fb_page and fb_token != "your_fb_access_token_here":
                try:
                    upload_reel(final_path, fb_cap, fb_hash, thumbnail_path=thumb_path)
                except Exception as e:
                    print(f"   ❌ Facebook upload failed: {e}")
            else:
                print("   ⚠️ Facebook credentials not set. Skipping.")

            # YouTube
            yt_success = False
            try:
                yt_res = upload_to_youtube(final_path, yt_titl, yt_desc, yt_tags)
                if yt_res and yt_res.get("id"):
                    # Save to posted_history.json for analytics healing
                    history_entry = {
                        "video_id": yt_res.get("id"),
                        "timestamp": datetime.datetime.now().isoformat(),
                        "script_state": state
                    }
                    history_file = "posted_history.json"
                    history_data = []
                    if os.path.exists(history_file):
                        with open(history_file, "r") as hf:
                            history_data = json.load(hf)
                    history_data.append(history_entry)
                    with open(history_file, "w") as hf:
                        json.dump(history_data, hf, indent=2)
                    
                    yt_success = True
            except Exception as e:
                print(f"   ❌ YouTube upload failed: {e}")

            # Instagram
            ig_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
            if ig_id and ig_id != "your_ig_business_id_here":
                try:
                    upload_to_instagram(final_path, ig_cap, ig_hash, thumbnail_path=thumb_path)
                except Exception as e:
                    print(f"   ❌ Instagram upload failed: {e}")
            else:
                print("   ⚠️ Instagram credentials not set. Skipping.")
                
            if yt_success:
                success = True
            else:
                print("   ⚠️ YouTube upload failed. Holding video and checkpoint for auto-retry.")
                success = False
                
        else:
            print("   ⚠️  User chose not to post. Skipping uploads.")
            print(f"   🎥 Video saved locally: {final_path}")
            # Save metadata so we can upload it later
            with open("final_reel_metadata.json", "w") as f:
                json.dump(state, f, indent=2)
            print("   📝 Metadata saved to final_reel_metadata.json so you can post it later.")
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
            temp_files = video_paths + [music_path, whoosh_path, impact_path, voice_path, voice_path + ".json"]
            for f in temp_files:
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
            print(f"   {video_paths} : Background videos")
            print(f"   temp_music.mp3    : Background music")
            print(f"   temp_whoosh.mp3   : Transition SFX")
            print(f"   temp_impact.wav   : Impact SFX")
            print(f"   temp_voice.mp3    : Voiceover audio")
            print(f"   pipeline_state.json: Checkpoint (resume marker)")


if __name__ == "__main__":
    main()
