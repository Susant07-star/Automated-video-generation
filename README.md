# 🚀 NextGenThoughts: Fully Automated Video Generation & Posting Pipeline

Welcome to the **NextGenThoughts Automation Pipeline**! This is a completely serverless, zero-cost, hands-free automation system that generates high-quality, highly engaging educational/psychology "Reels" and "Shorts" and posts them directly to your social media channels.

By leveraging a combination of free-tier AI tools, GitHub Actions, and a Netlify Dashboard, this system runs completely autonomously on a customizable daily schedule.

## ✨ Features

- **🧠 AI Content Masterclass:** Uses the Google Gemini API (`gemini-2.5-flash`) acting as a veteran scriptwriter. It generates gripping hooks, teaches deep psychological concepts (e.g., The Barnum Effect), and provides actionable takeaways without sounding like a textbook.
- **🛡️ Memory & Context:** The pipeline maintains a `generated_history.txt` log. Every time it runs, it reads past topics to ensure it **never repeats the same concept twice**.
- **🎥 Dynamic Video & SFX:** Automatically queries the **Pexels API** to download multiple high-quality vertical stock videos, stitching them together with auto-generated cinematic "whoosh" sound effects.
- **🎵 Ambient Background Music:** Pulls clean, cinematic, calm lo-fi music dynamically based on the mood.
- **🗣️ AI Voiceover:** Utilizes ElevenLabs or Microsoft Edge TTS to generate premium, pacing-perfect voiceovers.
- **🎬 Automated Assembly:** Uses `moviepy` to stitch the video, duck the background music under the voiceover, and overlay the text dynamically (with multi-platform font fallback ensuring bold, readable subtitles).
- **📈 Omnichannel SEO:** Generates perfectly optimized metadata for three platforms:
  - **YouTube Shorts:** Clickable titles with emojis, long-form descriptions, and 10-15 viral tags.
  - **Facebook Reels:** Conversational captions designed to drive comments and engagement.
  - **Instagram Reels:** Minimalist, aesthetic captions with deeply targeted niche hashtags.
- **🔁 API Key Rotation:** Built-in failover support for Gemini, Pexels, and ElevenLabs. If an API key hits a rate limit, the script instantly falls back to another key!

## ☁️ 100% Free Cloud Infrastructure

This project is built to run in the cloud for **$0/month** without you ever needing to touch a terminal.

1. **GitHub Actions (The Engine):** An hourly CRON job runs on GitHub Actions. It checks the schedule, installs dependencies, renders the video, posts it, and commits the history back to the repo.
2. **Netlify Dashboard (The Remote Control):** A beautiful, dark-mode web dashboard hosted on Netlify allows you to control the exact hours the bot posts every day, or trigger an instant "Post Now" override from your phone.

## 🛠️ Prerequisites (For Local Testing)

- Python 3.10+
- [ImageMagick](https://imagemagick.org/script/download.php) (Required by MoviePy for rendering text overlays).
- API Keys for Gemini, Pexels, ElevenLabs, and your social platforms.

## 🚀 Installation & Setup

### 1. The Repository
Fork or clone this repository to your own GitHub account.

### 2. Configure GitHub Secrets
Go to your repository settings on GitHub -> **Secrets and variables** -> **Actions**. Add the following repository secrets:
- `GEMINI_API_KEYS` (comma separated)
- `PEXELS_API_KEYS` (comma separated)
- `ELEVENLABS_API_KEYS` (comma separated)
- `FACEBOOK_PAGE_ACCESS_TOKEN`
- `FACEBOOK_PAGE_ID`
- `CLIENT_SECRET_JSON_B64` (Base64 encoded Google OAuth client secret)
- `YOUTUBE_TOKEN_JSON_B64` (Base64 encoded YouTube refresh token)

### 3. Deploy the Dashboard
1. Go to **Netlify.com** and sign in with GitHub.
2. Click **Add new site** -> **Import an existing project** -> **GitHub**.
3. Select this repository. Netlify will auto-detect the `netlify.toml` file.
4. Click **Deploy Site**.

### 4. Link the Dashboard
Open your new Netlify URL. It will ask for a **GitHub Personal Access Token (PAT)**. 
Create one with `repo` and `workflow` scopes in your GitHub Developer Settings, paste it in, and you now have full remote control over your automation!

## 🎯 Usage

### Cloud Usage (Recommended)
Simply open your Netlify dashboard, select the hours (UTC) you want the bot to post, and click **Save Schedule**. The GitHub Action will wake up every hour, check your config, and if it's time, it will generate and post a video completely hands-free.

### Local Usage
If you want to run it locally to test the rendering or generate a video without posting:

```bash
# Run interactively (asks for confirmation before posting)
python main.py

# Run in headless mode (auto-posts, used by the cloud runner)
python main.py --headless
```

---
*Built with ❤️ to automate the grind. Master your mind.*
