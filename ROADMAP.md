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

## 🔄 Phase 4: Content Quality — The Teacher Upgrade (IN PROGRESS — Top Priority)
* **Goal:** Stop sounding like a fact-presenter and start sounding like a passionate, relatable teacher. This is the #1 lever for audience growth.
* **Why:** Top psychology channels don't just present facts. They tell stories, use real-life relatable examples, and make the viewer feel like they are being taught a secret by a brilliant friend.
* **Implementation:**
  * **Storytelling Prompt Rewrite:** Completely rewrite the Gemini AI prompt to start every script with a relatable real-life scenario (e.g., "Imagine your friend just watched ONE YouTube video and now thinks he knows everything about investing...") before naming the concept.
  * **Emotional Arc:** Every script must follow: Hook → Relatable Story → Reveal the Concept → Why it Happens → How to Use/Spot it → Powerful Closing Line.
  * **Banned Phrases:** The AI will be explicitly forbidden from using robotic phrases like "This cognitive bias...", "Research shows...", "Studies have found...", "It's important to note...".
  * **Conversational Language:** Force the AI to write as if speaking to one specific person, not a crowd. Use "you", "your", "imagine", "think about it".

---

## 🔄 Phase 5: Karaoke Word-by-Word Subtitles (IN PROGRESS — Visual Upgrade)
* **Goal:** Replace the current static block text with dynamic, word-by-word highlighted subtitles (like Alex Hormozi and top viral channels use).
* **Why:** This is the #1 visual feature that increases watch time. When words pop up one at a time, the viewer's eyes have something to follow, keeping them locked in.
* **Implementation:**
  * Use the ElevenLabs word-level timestamp data (already being fetched!) to know the exact start and end time of every single word.
  * In `video_assembler.py`, instead of drawing one big text block, draw each word individually at its exact timestamp.
  * Highlight the current speaking word in a bright accent color (yellow or white) while the previous words fade to grey.
  * 3-4 words visible at a time, centered on screen, large and bold.

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
