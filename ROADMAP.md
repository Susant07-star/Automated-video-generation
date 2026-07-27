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

## 🔄 Phase 5: Karaoke Word-by-Word Subtitles (Implemented — Pending Test)
* **Goal:** Replace the current static block text with dynamic, word-by-word highlighted subtitles (like Alex Hormozi and top viral channels use).
* **Why:** This is the #1 visual feature that increases watch time. When words pop up one at a time, the viewer's eyes have something to follow, keeping them locked in.
* **Status:** Code implemented in `video_assembler.py`. Next video generated will use this system.
* **How it works:**
  * Words are grouped into chunks of 4 at a time on screen.
  * As each word is spoken, it turns **bright yellow**.
  * Words already spoken turn **light grey**.
  * Upcoming words stay **white**.
  * Powered by ElevenLabs word-level timestamps (exact millisecond accuracy).

---

## 📋 Phase 6: Hindi Language Channel (PLANNED)
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

## 📋 Phase 7: Long-Form Deep Dive Videos (PLANNED — Future)
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

## 📋 Phase 8: Visual Branding & Logo Overlay (PLANNED)
* **Goal:** Build brand authority and prevent content theft.
* **Implementation:**
  * Prepare a transparent `.png` logo for `NextGenThoughts`.
  * Overlay it in the top corner of the video at 50% opacity.
  * Note: Disable on YouTube Shorts thumbnails to prevent demonetization triggers.

---
*"We are building the most powerful free automated psychology content machine on the internet."*
