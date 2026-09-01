# NextGenThoughts Automation Roadmap

This document outlines the strategic upgrades for the `Automated-video-generation` pipeline. We have successfully evolved the project from a simple local script into a fully autonomous, serverless cloud pipeline!

---

## ✅ Phase 1: High-Retention Video Editing (Completed)
* **Goal:** Maximize viewer retention and watch time by keeping the visuals dynamic.
* **Status:** Finished! The script now stitches 4-8 different videos together matching the spoken topics, overlaid with cinematic 'whoosh' transitions and ducked background music.

---

## ✅ Phase 2: Omnichannel Auto-Posting (Completed / Partially Active)
* **Goal:** Triple the reach of every generated video by publishing it to all major short-form platforms simultaneously.
* **Status:** Finished!
  * **YouTube Shorts:** Integrated and active via OAuth.
  * **Facebook Reels:** Integrated and active via Graph API.
  * **Instagram Reels:** Code structure exists; waiting on the user to create the Instagram account to link it.

---

## ✅ Phase 3: Cloud Cron Scheduling (Completed)
* **Goal:** Remove the need to manually run `python main.py` or leave a local PC turned on.
* **Status:** Finished! The pipeline runs 100% free via **GitHub Actions**, triggered hourly (at minute 07 to avoid queue delays). A beautiful **Netlify Control Dashboard** allows the user to select the exact posting hours dynamically without touching code.

---

## ✅ Phase 4: Content Quality — The Teacher Upgrade (Completed)
* **Goal:** Stop sounding like a fact-presenter and start sounding like a passionate, relatable teacher. This is the #1 lever for audience growth.
* **Status:** Finished! The Gemini prompt has been completely rewritten to follow the emotional arc: Hook (vivid scene) → Reveal (name the concept) → Masterclass (relatable story) → Power Move (closing punch line). Robotic phrases are explicitly banned.

---

## ✅ Phase 5: Karaoke Word-by-Word Subtitles (Completed)
* **Goal:** Replace the current static block text with dynamic, word-by-word highlighted subtitles (like Alex Hormozi and top viral channels use).
* **Status:** Finished! The script renders word-by-word karaoke subtitles using exact millisecond timestamps from ElevenLabs.

---

## ✅ Phase 6: Cinematic Polish (Completed)
* **Goal:** Increase the production value to match top 1% editing teams.
* **Status:** Finished!
  * **Visual Hook:** Added a Ken Burns zoom to the very first clip.
  * **Impact SFX:** Automatically detects power words ("secret", "danger", etc.) and inserts a deep cinematic bass boom underneath them.
  * **Context-Aware B-Roll:** Gemini now generates hyper-literal visual search terms instead of abstract psychological concepts.
  * **Instrumental Music:** Forced Jamendo API to only return instrumental music to prevent vocal clashing.

---

## 🔄 Phase 7: Viral Growth & Engagement Enhancements (IN PROGRESS)
* **Goal:** Implement algorithm-friendly hooks, dynamic visuals, and advanced editing techniques to increase view velocity and audience retention.
* **Status:** ✅ Complete (2 features skipped with justification).
  * ✅ **Story/Secret Hook Archetypes:** 7 rotating hook styles (Forbidden Secret, Personal Confession, Counter-Intuitive Challenge, Threat/Warning, Vivid Scene, Rhetorical Trap, Shocking Statistic) are randomly selected each run so every video opens differently.
  * ✅ **Loopable Script Design:** The AI is now instructed to make the final sentence echo the opening hook, creating a seamless infinite-loop effect for YouTube Shorts replays (boosts watch-time %).
  * ✅ **Dynamic B-Roll Cuts:** Clips now cut on natural speech pauses (≥ 0.35s gaps between words) detected from the ElevenLabs timestamp JSON, so every B-roll change lands on a breath/sentence boundary — never mid-word.
  * ✅ **Micro-Animation Pop-In:** The active (yellow) subtitle word is rendered 16% larger than surrounding words, creating a visual "pop" effect in sync with the narrator's speech.
  * ❌ **Emoji Injection:** Skipped — Pillow cannot reliably render color emoji glyphs on Windows (Arial Bold has no emoji support). Would require PNG overlay pipeline; revisit if needed.
  * ❌ **Ambient Bed Tracks & Risers:** Skipped — audio mix is already complex (music + impact SFX + whoosh). Adding tension drones/rain on top creates sonic chaos that’s difficult to tune automatically. The bass boom SFX already delivers the cinematic punch.
  * ❌ **A/B Testing Generation:** Skipped — no analytics feedback loop yet (no code to read back view counts from YouTube/Instagram API). Without a measure-and-iterate pipeline, it’s just 3x the content with no learning. Revisit at 10K+ subscribers.
  * ✅ **Automated Thumbnail Extraction:** After each render, ffmpeg grabs the frame at the 3rd spoken word's timestamp (deep in the hook, subtitle fully visible). The JPG is saved as `final_reel_thumbnail.jpg` and automatically set as the cover photo for both Instagram (`cover_url`) and Facebook (`thumb_url`) Reels uploads.

---

## ✅ Phase 8: Advanced Retention & Voice Design (COMPLETE)
* **Goal:** Implement Hollywood-style audio ducking, a CTA overlay for saves, and a professional karaoke subtitle system.
* **Status:** ✅ Complete (1 feature skipped with justification).
  * ✅ **Idea A (Dynamic Ducking):** Music swells between sentences and ducks during speech (already implemented in audio mix).
  * ✅ **Idea C (CTA Overlay):** A sleek, modern "Save this for later" pill graphic pops up in the last 3 seconds. Built using clean Pillow text rendering to avoid color emoji issues.
  * ✅ **Subtitle Micro-Animation Fix:** Completely rewrote `create_karaoke_subtitle_image` to fix the vertical-jumping layout bug. Key improvements:
    * **Fixed-height row:** Row height is now reserved using the active word's size upfront, so the layout never shifts when a new word activates.
    * **Vertical centering:** All words are now perfectly center-aligned within the stable row.
    * **Clean 8-direction stroke:** Replaced the blurry 121-iteration stroke loop with a crisp 8-point offset stroke.
    * **Soft glow effect:** Active yellow word gets a subtle golden halo for a premium, professional look.
  * ❌ **Idea D (Custom Voice):** Skipped — ElevenLabs restricts sharing custom cloned voices across accounts. Reverted to standard high-quality voices (e.g., Adam).

---

## ✅ Phase 9: Self-Healing Analytics System (COMPLETE)
* **Goal:** Build a closed-loop AI system that tracks video performance and automatically rewrites its own generation rules to improve future videos.
* **Status:** ✅ Complete.
  * ✅ **The Tracker (`main.py` & `cartoon_main.py`):** After every successful YouTube upload, the pipeline saves the `video_id`, timestamp, and full script state to `posted_history.json` (and `posted_history_cartoon.json` for Cartoon Plus).
  * ✅ **The Doctor (`heal.py` & `heal_cartoon.py`):** A standalone script that:
    * Finds all unanalyzed videos that are 3–20 days old (3-day minimum ensures YouTube AVD data is available; 20-day max avoids stale data).
    * Fetches Views, Likes, Comments (Data API) and Average View Duration (Analytics API — requires `yt-analytics.readonly` OAuth scope).
    * Sends data to **Gemini 2.5-Pro** (upgraded from 1.5-Pro for sharper strategic reasoning).
    * Generates 3–5 new high-impact rules and overwrites `ai_directives.txt`.
    * Marks each processed video `"analyzed": true` so it's never double-counted. Videos older than 20 days are auto-expired.
    * Fully independent versions for NextGenThoughts and Cartoon Plus channels.
  * ✅ **The Healer (`content_generator.py`):** Before generating each script, loads the correct directives file (`ai_directives.txt` or `ai_directives_cartoon.txt`) and injects it as a `CRITICAL DIRECTIVES` block into the Gemini system prompt.
  * ✅ **Dashboard Integration (`dashboard/index.html` & `cartoon.html`):** Added a "🩺 Self-Healing Analytics" section to both dashboards. Users can select the day of the week for automatic analysis and trigger an immediate analysis with the "⚡ Analyze Now" button.
  * ✅ **Scheduler Integration (`scheduler.py`):** On the configured Analytics Day, the scheduler runs `heal.py` before generating the first video of the day, so new videos immediately benefit from the latest directives.

---

## 📋 Phase 10: Hindi Language Channel (PLANNED)
* **Goal:** Launch a second, dedicated Hindi psychology channel to tap into the massive 500M+ Hindi-speaking YouTube audience where competition is significantly lower.
* **Strategy — Two Separate Channels (NOT the same channel):**
  * Mixing Hindi and English on one channel confuses the YouTube algorithm and splits your audience. Each channel must have a 100% focused identity.
  * **Channel 1 (English):** NextGenThoughts — current channel, global audience.
  * **Channel 2 (Hindi):** NextGenThoughts Hindi (or a unique Hindi brand name) — dedicated Hindi audience.
* **Implementation:**
  * Add a `language` field to `schedule_config.json` (e.g., `"en"` or `"hi"`).
  * Update `content_generator.py` to prompt Gemini to generate the entire script in Hindi when `language = "hi"`.
  * Add a second ElevenLabs voice profile that speaks Hindi natively (e.g., "Aria" or a Hindi-supported voice).
  * Add a second set of YouTube OAuth credentials for the Hindi channel to GitHub Secrets.
  * Run two separate pipelines: one English, one Hindi, posting to their own channels simultaneously.

---

## 📋 Phase 11: Long-Form Deep Dive Videos (PLANNED — Future)
* **Goal:** Build deep authority and a loyal community, not just a casual viral audience.
* **Strategy:**
  * Do NOT start with long-form content. Build the short-form audience to 1,000-5,000 subscribers first. Shorts are the fastest discovery engine.
  * Once Shorts are growing, release **one 8-12 minute "Deep Dive" video per week** on the same topic as the most popular Short of that week.
  * The Short acts as the trailer/hook. The Long-Form is where viewers who want more go.
* **Implementation:**
  * A separate `long_form_generator.py` that prompts Gemini for a full 800-1200 word script.
  * A separate rendering pipeline that produces a 16:9 (landscape) video instead of 9:16 (portrait).
  * Triggered manually or on a weekly cron schedule.

---

## 📋 Phase 12: Visual Branding & Logo Overlay (PLANNED)
* **Goal:** Build brand authority and prevent content theft.
* **Implementation:**
  * Prepare a transparent `.png` logo for `NextGenThoughts`.
  * Overlay it in the top corner of the video at 50% opacity.
  * Note: Disable on YouTube Shorts thumbnails to prevent demonetization triggers.

---
*"We are building the most powerful free automated psychology content machine on the internet."*
