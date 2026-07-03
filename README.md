# 🚀 Automated Motivational Video Generator

Welcome to the **Automated Motivational Video Generator**! This pipeline is designed to completely automate the creation and publishing of engaging, motivational Reels for Facebook (or any other short-form platform).

By leveraging powerful free-tier AI tools, this Python script generates quotes, fetches stock videos and music, synthesizes AI voiceovers, and stitches them all together into a polished 9:16 vertical video.

## ✨ Features

- **🧠 AI Content Generation:** Uses the Google Gemini API (`google-genai`) to generate unique, powerful motivational quotes, post captions, and relevant hashtags.
- **🎥 Dynamic Video Sourcing:** Automatically queries the **Pexels API** to download high-quality, royalty-free vertical stock videos based on the AI-generated theme.
- **🎵 Background Music:** Connects to the **Pixabay API** to fetch cinematic/lo-fi royalty-free background music.
- **🗣️ AI Voiceover:** Utilizes `edge-tts` to generate premium Microsoft AI voices, reading the quote with perfect pacing and tone.
- **🎬 Automated Assembly:** Uses `moviepy` to stitch the video, duck the background music under the voiceover, and overlay the quote text dynamically.
- **🔁 API Key Rotation:** Built-in failover support for Gemini, Pexels, and Pixabay. If an API key hits a rate limit, the script instantly falls back to another key in your `.env` file to ensure the pipeline never breaks!
- **🌐 Auto-Publishing (Optional):** Integrated with the Facebook Graph API to automatically upload the finished Reel directly to your Facebook Page with captions and tags.

## 🛠️ Prerequisites

- Python 3.10+
- [ImageMagick](https://imagemagick.org/script/download.php) (Required by MoviePy for rendering text overlays. Ensure it is added to your system PATH).
- API Keys for Gemini, Pexels, Pixabay, and Facebook (Graph API).

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Susant07-star/Automated-video-generation.git
   cd Automated-video-generation
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the root directory and add your API keys. You can add multiple keys separated by commas for automatic rotation!
   ```env
   GEMINI_API_KEYS=key1,key2,key3
   PEXELS_API_KEYS=key1,key2
   PIXABAY_API_KEYS=key1
   FACEBOOK_PAGE_ACCESS_TOKEN=your_fb_access_token_here
   FACEBOOK_PAGE_ID=your_fb_page_id_here
   ```

## 🎯 Usage

Simply run the orchestrator script:

```bash
python main.py
```

### What happens when you run it?
1. The AI generates a theme, quote, and caption.
2. Background media (video and audio) are downloaded to temporary files.
3. The AI voiceover is synthesized.
4. `moviepy` combines the assets, ducks the music, overlays the text, and renders `final_reel.mp4`.
5. (Optional) If Facebook credentials are provided, it uploads the Reel.
6. Temporary media files are cleaned up!

## ☁️ Deployment

This project is perfectly suited for platforms like **Render**, **Heroku**, or **AWS EC2**. Just set up a daily CRON job to run `main.py`, and your Facebook Page will grow on autopilot!

## 🤝 Contributing

Contributions are welcome! Feel free to open an issue or submit a pull request.

---
*Built with ❤️ to automate the grind.*
