import os
import json
import base64
import asyncio
import requests
import edge_tts
from src.api_manager import elevenlabs_rotator
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# BRAND VOICE
# Voice ID for Adam (standard ElevenLabs voice available on free tier)
# Voice ID: pNInz6obpgDQGcFmaJcg
# ============================================================
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJcg")
ELEVENLABS_VOICE_NAME = os.getenv("ELEVENLABS_VOICE_NAME", "Adam")

# edge-tts fallback voices per profile
FALLBACK_VOICE = "en-US-GuyNeural"           # Motivational (English)
FALLBACK_VOICE_CARTOON = "hi-IN-SwaraNeural" # Hindi female voice — lighter, clearer, suits comedy

def _extract_word_timestamps(alignment: dict) -> list:
    """
    Parses ElevenLabs character-level alignment into word-level timestamps.
    Returns: [{'word': 'Hello', 'start': 0.1, 'end': 0.5}, ...]
    """
    words = []
    current_word = ""
    current_start = None
    
    chars = alignment.get('characters', [])
    starts = alignment.get('character_start_times_seconds', [])
    ends = alignment.get('character_end_times_seconds', [])
    
    for i, char in enumerate(chars):
        if char.strip():  # non-whitespace
            if current_word == "":
                current_start = starts[i]
            current_word += char
        else:
            if current_word:
                words.append({
                    "word": current_word,
                    "start": current_start,
                    "end": ends[i-1]
                })
                current_word = ""
                
    # Add the last word if exists
    if current_word:
        words.append({
            "word": current_word,
            "start": current_start,
            "end": ends[-1]
        })
        
    return words

VOICE_MAP_FILE = "elevenlabs_voice_map.json"

def ensure_iconic_voice_exists(api_key: str) -> str:
    """
    Checks if the API key already has the 'NextGenThoughts voice' mapped.
    If not, checks ElevenLabs if it exists. If not, clones it using reference_voice.mp3.
    Returns the voice_id.
    """
    key_last4 = api_key[-4:]
    
    # 1. Check local map
    if os.path.exists(VOICE_MAP_FILE):
        with open(VOICE_MAP_FILE, "r") as f:
            voice_map = json.load(f)
    else:
        voice_map = {}
        
    if key_last4 in voice_map:
        return voice_map[key_last4]
        
    # 2. Check ElevenLabs account for existing voice
    headers = {"xi-api-key": api_key}
    print(f"   🔍 Checking ElevenLabs account (key ...{key_last4}) for 'NextGenThoughts voice'...")
    try:
        resp = requests.get("https://api.elevenlabs.io/v1/voices", headers=headers, timeout=15)
        resp.raise_for_status()
        voices = resp.json().get("voices", [])
        for v in voices:
            if v.get("name") == "NextGenThoughts voice" or v.get("voice_id") == ELEVENLABS_VOICE_ID:
                vid = v.get("voice_id")
                voice_map[key_last4] = vid
                with open(VOICE_MAP_FILE, "w") as f:
                    json.dump(voice_map, f, indent=2)
                print(f"   ✅ Found existing voice: {vid}")
                return vid
    except Exception as e:
        print(f"   ⚠️ Failed to get voices for key {key_last4}: {e}")
        
    # 3. Clone the voice
    print(f"   🚀 'NextGenThoughts voice' not found on key ...{key_last4}. Cloning from reference_voice.mp3...")
    if not os.path.exists("reference_voice.mp3"):
        print("   ❌ reference_voice.mp3 missing! Cannot clone voice. Falling back to default.")
        return ELEVENLABS_VOICE_ID
        
    url = "https://api.elevenlabs.io/v1/voices/add"
    headers = {
        "xi-api-key": api_key,
        "Accept": "application/json"
    }
    data = {
        "name": "NextGenThoughts voice",
        "description": "Auto-cloned iconic channel voice"
    }
    
    try:
        with open("reference_voice.mp3", "rb") as f:
            files = [
                ("files", ("reference_voice.mp3", f, "audio/mpeg"))
            ]
            resp = requests.post(url, headers=headers, data=data, files=files, timeout=60)
            resp.raise_for_status()
            vid = resp.json().get("voice_id")
            
            voice_map[key_last4] = vid
            with open(VOICE_MAP_FILE, "w") as f:
                json.dump(voice_map, f, indent=2)
                
            print(f"   ✅ Voice successfully cloned! New Voice ID: {vid}")
            return vid
    except Exception as e:
        print(f"   ❌ Failed to clone voice for key {key_last4}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Details: {e.response.text}")
        return ELEVENLABS_VOICE_ID

def _get_valid_voice_id(api_key: str, preferred_voice_name: str = "Adam") -> str:
    """Checks if the preferred voice exists by NAME. If not, grabs the first available voice."""
    try:
        url = "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": api_key}
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            voices = resp.json().get("voices", [])
            
            # 1. Search by exact name match (case-insensitive)
            for v in voices:
                if v.get("name", "").lower() == preferred_voice_name.lower():
                    return v.get("voice_id")
                    
            # 2. Search by partial name match
            for v in voices:
                if preferred_voice_name.lower() in v.get("name", "").lower():
                    return v.get("voice_id")
            
            # 3. Fallback to whatever is available
            if voices:
                fallback = voices[0]
                print(f"   ⚠️ Voice '{preferred_voice_name}' not found on this account. Auto-falling back to '{fallback['name']}' ({fallback['voice_id']})")
                return fallback["voice_id"]
    except Exception:
        pass
    return ELEVENLABS_VOICE_ID

def _generate_with_elevenlabs(text: str, output_filename: str, api_key: str, voice_id: str) -> bool:
    """
    Generates voiceover using ElevenLabs API with timestamps.
    Saves audio to `output_filename` and timestamps to `output_filename.json`.
    """
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
        
        headers = {
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }

        # Speak the script exactly as Gemini wrote it — no generic wrappers.
        # The quote itself IS the script. Varied, creative, no repeated lines.
        full_script = text

        data = {
            "text": full_script,
            "model_id": "eleven_turbo_v2_5",  # Turbo v2.5 is much more conversational and human-like
            "voice_settings": {
                # Very low stability = highly expressive, natural human variations (not robotic)
                "stability": 0.20,
                # Lower similarity allows the AI to adapt its tone dynamically
                "similarity_boost": 0.75,
                # High style = strong emotional emphasis
                "style": 0.70,
                "use_speaker_boost": True
            }
        }

        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code != 200:
            print(f"ElevenLabs error: {response.text}")
            return False
            
        result = response.json()
        audio_bytes = base64.b64decode(result["audio_base64"])
        alignment = result.get("alignment", {})

        # Save audio to file
        with open(output_filename, "wb") as f:
            f.write(audio_bytes)
            
        # Parse and save word timestamps
        word_timestamps = _extract_word_timestamps(alignment)
        timestamps_file = output_filename + ".json"
        with open(timestamps_file, "w") as f:
            json.dump(word_timestamps, f)

        print(f"ElevenLabs voiceover & timestamps generated successfully.")
        return True

    except Exception as e:
        print(f"ElevenLabs unexpected error: {e}")
        return False

async def _generate_fallback_async(text: str, output_filename: str, profile: str = "motivational"):
    """Fallback to edge-tts. Uses a Hindi expressive voice for the cartoon profile."""
    voice = FALLBACK_VOICE_CARTOON if profile == "cartoon" else FALLBACK_VOICE
    
    if profile == "cartoon":
        # Hindi TTS with slightly faster rate for energetic/funny delivery
        communicate = edge_tts.Communicate(
            text, voice,
            rate="+10%",   # Slightly faster for lively Hindi comedy pacing
            volume="+20%", # Slightly louder for clarity
        )
    else:
        # Standard edge-tts for motivational (if ever used)
        communicate = edge_tts.Communicate(
            text, voice,
            rate="-5%",
        )
    
    await communicate.save(output_filename)
    
    # Generate fake evenly-spaced timestamps so dynamic subtitles still work
    try:
        from moviepy.editor import AudioFileClip
        audio = AudioFileClip(output_filename)
        duration = audio.duration
        audio.close()
        
        words = text.split()
        if words:
            time_per_word = duration / len(words)
            timestamps = []
            for i, word in enumerate(words):
                timestamps.append({
                    "word": word,
                    "start": i * time_per_word,
                    "end": (i + 1) * time_per_word
                })
            with open(output_filename + ".json", "w") as f:
                json.dump(timestamps, f, indent=4)
        else:
            with open(output_filename + ".json", "w") as f:
                json.dump([], f)
    except Exception as e:
        print(f"Failed to generate fake timestamps: {e}")
        with open(output_filename + ".json", "w") as f:
            json.dump([], f)

def generate_voiceover(text: str, output_filename="temp_voice.mp3", profile="motivational") -> str:
    """
    Generates voiceover using ElevenLabs (motivational profile) or edge-tts (cartoon profile).
    - motivational: Uses ElevenLabs with the default Adam voice (NO cloning).
    - cartoon: Skips ElevenLabs entirely and uses hi-IN-SwaraNeural (Hindi) via edge-tts.
    Returns the path to the MP3. (A matching .json file will also be created).
    """
    # ── Cartoon Plus: go straight to Hindi edge-tts, skip ElevenLabs entirely ──
    if profile == "cartoon":
        print("Cartoon Plus profile — using Hindi edge-tts voice (hi-IN-SwaraNeural)...")
        asyncio.run(_generate_fallback_async(text, output_filename, profile="cartoon"))
        return output_filename

    # ── Motivational: use ElevenLabs with the default Adam voice (no cloning) ──
    while elevenlabs_rotator.has_keys():
        current_key = elevenlabs_rotator.get_random_key()
        # Verify the voice exists in this key's library, or auto-fallback to the first available
        voice_id = _get_valid_voice_id(current_key, ELEVENLABS_VOICE_NAME)
        
        print(f"Generating voiceover with ElevenLabs (Voice: {voice_id} - {ELEVENLABS_VOICE_NAME}, with timestamps)...")
        success = _generate_with_elevenlabs(text, output_filename, current_key, voice_id)
        if success:
            return output_filename
        else:
            elevenlabs_rotator.remove_key(current_key)

    # Fail if all ElevenLabs keys are exhausted
    print("❌ All ElevenLabs keys exhausted or failed.")
    raise Exception(
        f"ElevenLabs generation failed. If you got 'voice_not_found', make sure to add the voice ID "
        f"'{ELEVENLABS_VOICE_ID}' to your ElevenLabs Voice Library, or change ELEVENLABS_VOICE_ID in your .env file."
    )

