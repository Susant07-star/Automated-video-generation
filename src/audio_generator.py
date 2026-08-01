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
# BRAND VOICE — DO NOT CHANGE
# This is the custom iconic voice of the channel.
# Voice ID: qeVMjfAnyqoR0DeCeeXL
# ============================================================
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "qeVMjfAnyqoR0DeCeeXL")

# edge-tts fallback voice
FALLBACK_VOICE = "en-US-GuyNeural"

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

async def _generate_fallback_async(text: str, output_filename: str):
    """Fallback to edge-tts with SSML for emotional delivery."""
    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    ssml_sentences = "".join(
        f'<break time="400ms"/>{s}.<break time="700ms"/>' for s in sentences
    )
    ssml = f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
        xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="en-US">
        <voice name="{FALLBACK_VOICE}">
            <prosody rate="-10%" pitch="+1Hz">
                <break time="300ms"/>Here is your motivation for today.<break time="800ms"/>
                {ssml_sentences}
                <break time="600ms"/>Follow for your daily motivation.
            </prosody>
        </voice>
    </speak>"""
    communicate = edge_tts.Communicate(ssml, FALLBACK_VOICE)
    await communicate.save(output_filename)
    
    # Save a fake/empty JSON timestamp file to prevent assembler crashes
    with open(output_filename + ".json", "w") as f:
        json.dump([], f)

def generate_voiceover(text: str, output_filename="temp_voice.mp3") -> str:
    """
    Generates voiceover using ElevenLabs (brand voice) with key rotation.
    Falls back to edge-tts if keys are exhausted.
    Returns the path to the MP3. (A matching .json file will also be created).
    """
    # Try ElevenLabs first
    while elevenlabs_rotator.has_keys():
        current_key = elevenlabs_rotator.get_random_key()
        
        # Ensure voice exists and get its ID
        voice_id = ensure_iconic_voice_exists(current_key)
        
        print(f"Generating voiceover with ElevenLabs (Voice: {voice_id}, with timestamps)...")
        success = _generate_with_elevenlabs(text, output_filename, current_key, voice_id)
        if success:
            return output_filename
        else:
            elevenlabs_rotator.remove_key(current_key)

    # Fallback to edge-tts
    print("All ElevenLabs keys exhausted. Falling back to edge-tts...")
    asyncio.run(_generate_fallback_async(text, output_filename))
    return output_filename
