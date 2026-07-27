import os
import requests
import random
import wave
from urllib.parse import quote_plus
import numpy as np
from src.api_manager import pexels_rotator, pixabay_rotator

REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}


def download_file(url: str, dest_path: str):
    temp_path = f"{dest_path}.part"
    bytes_written = 0

    try:
        response = requests.get(url, stream=True, headers=REQUEST_HEADERS, timeout=(10, 90))
        response.raise_for_status()
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    bytes_written += len(chunk)
                    f.write(chunk)

        if bytes_written < 1024:
            raise ValueError(f"Downloaded file from {url} was unexpectedly small ({bytes_written} bytes).")

        os.replace(temp_path, dest_path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

    return dest_path


def create_local_cinematic_music(output_filename="temp_music.wav", duration=60, sample_rate=44100):
    """
    Generates a simple copyright-safe ambient music bed locally.
    This keeps the pipeline working even when every remote music source blocks downloads.
    """
    print("Generating local copyright-safe ambient music fallback...")

    total_samples = int(duration * sample_rate)
    audio = np.zeros(total_samples, dtype=np.float32)
    chords = [
        [110.00, 164.81, 220.00, 329.63],
        [98.00, 146.83, 196.00, 293.66],
        [130.81, 196.00, 261.63, 392.00],
        [87.31, 130.81, 174.61, 261.63],
    ]
    chord_duration = 8.0

    for chord_index, start in enumerate(np.arange(0, duration, chord_duration)):
        end = min(start + chord_duration, duration)
        start_i = int(start * sample_rate)
        end_i = int(end * sample_rate)
        local_t = np.linspace(0, end - start, end_i - start_i, endpoint=False)

        pad = np.zeros_like(local_t, dtype=np.float32)
        for freq in chords[chord_index % len(chords)]:
            pad += 0.12 * np.sin(2 * np.pi * freq * local_t)
            pad += 0.04 * np.sin(2 * np.pi * freq * 2 * local_t)

        fade_samples = min(int(1.5 * sample_rate), len(local_t) // 2)
        envelope = np.ones_like(local_t, dtype=np.float32)
        if fade_samples > 0:
            fade = np.linspace(0, 1, fade_samples, dtype=np.float32)
            envelope[:fade_samples] *= fade
            envelope[-fade_samples:] *= fade[::-1]

        audio[start_i:end_i] += pad * envelope

    # Gentle pulse for momentum under the voiceover.
    t = np.linspace(0, duration, total_samples, endpoint=False)
    pulse = 0.06 * np.sin(2 * np.pi * 55 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * t))
    audio += pulse.astype(np.float32)

    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.45

    pcm = (audio * 32767).astype(np.int16)
    with wave.open(output_filename, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())

    return output_filename


def fetch_background_video(keywords: list[str], output_filenames: list[str]):
    for kw, out_file in zip(keywords, output_filenames):
        _fetch_single_video(kw, out_file)

def _fetch_single_video(keyword: str, output_filename: str):
    url = f"https://api.pexels.com/videos/search?query={quote_plus(keyword)}&orientation=portrait&size=large&per_page=15"

    while pexels_rotator.has_keys():
        current_key = pexels_rotator.get_random_key()
        headers = {"Authorization": current_key}

        response = requests.get(url, headers=headers)
        if response.status_code in [429, 403]:
            print(f"Pexels rate limit hit on key {current_key[:5]}... Rotating...")
            pexels_rotator.remove_key(current_key)
            continue

        response.raise_for_status()
        data = response.json()

        if not data.get("videos"):
            print(f"No videos found for keyword '{keyword}', falling back to 'nature'.")
            fallback_url = f"https://api.pexels.com/videos/search?query=nature&orientation=portrait&size=large&per_page=15"
            response = requests.get(fallback_url, headers=headers)
            data = response.json()

        videos = data.get("videos", [])
        if not videos:
            raise Exception("Could not find any videos on Pexels.")

        video = random.choice(videos)
        video_files = video.get("video_files", [])

        # ── Pick the best 1080p (or closest-below) file ──────────────────
        # Target: width <= 1080 for portrait (height <= 1920).
        # Sort by width descending so we take the best quality that still fits.
        TARGET_W = 1080
        portrait_files = sorted(
            [f for f in video_files if f.get('width', 9999) <= TARGET_W],
            key=lambda f: f.get('width', 0),
            reverse=True
        )
        if not portrait_files:
            # Nothing ≤1080px — grab the absolute smallest to minimise download
            portrait_files = sorted(video_files, key=lambda f: f.get('width', 9999))

        best_file = portrait_files[0]
        video_url = best_file['link']
        w, h = best_file.get('width', '?'), best_file.get('height', '?')
        print(f"Downloading {w}x{h} video (capped at 1080p) from Pexels...")
        return download_file(video_url, output_filename)

    raise Exception("All Pexels API keys exhausted.")


def fetch_background_music(keyword: str, output_filename: str = "temp_music.mp3") -> str:
    """
    Fetches background music using a 3-tier strategy:

    Tier 1 — Jamendo API (FREE, no approval, 500k+ CC-licensed tracks)
              Register a free client_id at https://devportal.jamendo.com
              Add JAMENDO_CLIENT_ID=your_id to .env for access.

    Tier 2 — Hardcoded CDN pool (25 tracks, all tested 200 OK, no auth needed)
              SoundHelix (17 tracks) + Fesliyan Studios (8 tracks)

    Tier 3 — Locally synthesised ambient music (always works, no internet needed)
    """

    # ── Tier 1: Jamendo API ───────────────────────────────────────────────────
    jamendo_client_id = os.getenv("JAMENDO_CLIENT_ID", "")
    if jamendo_client_id:
        mood_map = {
            "inspirational": "inspiring",
            "cinematic": "epic",
            "epic": "epic",
            "motivational": "inspiring",
            "uplifting": "positive",
            "calm": "relaxing",
        }
        tags = mood_map.get(keyword.lower().split()[0], "inspiring")
        url = (
            f"https://api.jamendo.com/v3.0/tracks/?client_id={jamendo_client_id}"
            f"&format=json&limit=10&audiodlformat=mp32"
            f"&tags={tags}&order=popularity_total"
        )
        try:
            resp = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
            if resp.status_code == 200:
                tracks = resp.json().get("results", [])
                if tracks:
                    track = random.choice(tracks[:5])
                    audio_url = track.get("audiodownload") or track.get("audio")
                    name = track.get("name", "track")
                    print(f"[Jamendo] Downloading '{name}'...")
                    return download_file(audio_url, output_filename)
        except Exception as e:
            print(f"[Jamendo] Error: {e}. Moving to CDN pool...")
    else:
        print("[Music] No JAMENDO_CLIENT_ID set. Skipping Jamendo (add it to .env for 500k+ CC tracks).")

    # ── Tier 2: Hardcoded CDN pool (25 verified tracks, zero auth) ────────────
    # SoundHelix: 17 royalty-free tracks — https://www.soundhelix.com
    # Fesliyan Studios: epic/cinematic tracks — https://www.fesliyanstudios.com
    CDN_TRACKS = [
        # SoundHelix — all 17 tracks (audio/mpeg, tested 200 OK)
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-5.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-6.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-7.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-8.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-9.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-10.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-11.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-12.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-13.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-14.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-15.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-16.mp3",
        "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-17.mp3",
        # Fesliyan Studios — Epic/Cinematic/Motivational (tested 200 OK)
        "https://www.fesliyanstudios.com/play-mp3/387",   # Epic Motivation
        "https://www.fesliyanstudios.com/play-mp3/4386",  # Inspiring Moment
        "https://www.fesliyanstudios.com/play-mp3/2389",  # Rise Up
        "https://www.fesliyanstudios.com/play-mp3/511",   # Its A New Day
        "https://www.fesliyanstudios.com/play-mp3/4585",  # Uplifting Corporate
        "https://www.fesliyanstudios.com/play-mp3/4396",  # Positive Motivation
        "https://www.fesliyanstudios.com/play-mp3/4106",  # Powerful Cinematic
        "https://www.fesliyanstudios.com/play-mp3/4607",  # Heroes Journey
    ]

    print("[Music] Selecting from 25-track CDN pool (SoundHelix + Fesliyan Studios)...")
    for track_url in random.sample(CDN_TRACKS, len(CDN_TRACKS)):
        try:
            print(f"  Downloading: {track_url.split('/')[-1] or track_url[-30:]}")
            return download_file(track_url, output_filename)
        except Exception as e:
            print(f"  CDN track failed: {e} — trying next...")

    # ── Tier 3: Local synthesis (always works, no internet) ───────────────────
    print("[Music] All CDN sources failed. Generating local ambient music...")
    local_output = os.path.splitext(output_filename)[0] + ".wav"
    return create_local_cinematic_music(local_output)

def fetch_whoosh_sfx(output_filename="temp_whoosh.wav"):
    """
    Generates a high-quality cinematic whoosh sound effect locally using numpy.
    100% reliable, no internet required, copyright-free.
    """
    print("Generating local cinematic 'whoosh' transition SFX...")
    sample_rate = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    
    # White noise base
    noise = np.random.normal(0, 1, len(t))
    
    # Fast attack, slow decay envelope for the whoosh shape
    envelope = (t * 5) * np.exp(-t * 6)
    
    # Apply a sweeping low-pass filter effect using a sine wave frequency modulation
    # (Simulating a swoosh by changing pitch)
    sweep = np.sin(2 * np.pi * (100 + 400 * t) * t)
    
    audio = noise * envelope * sweep
    
    # Normalize
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.8
        
    pcm = (audio * 32767).astype(np.int16)
    with wave.open(output_filename, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())
        
    return output_filename


if __name__ == "__main__":
    pass

