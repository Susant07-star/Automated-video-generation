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
# "Adam" by ElevenLabs: deep, authoritative, human, motivational.
# This is the permanent voice identity of the channel.
# Voice ID: pNInz6obpgDQGcFmaJgB
# ============================================================
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")

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


def _generate_with_elevenlabs(text: str, output_filename: str, api_key: str) -> bool:
    """
    Generates voiceover using ElevenLabs API with timestamps.
    Saves audio to `output_filename` and timestamps to `output_filename.json`.
    """
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/with-timestamps"
        
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
        print(f"Generating voiceover with ElevenLabs (Adam, with timestamps)...")
        success = _generate_with_elevenlabs(text, output_filename, current_key)
        if success:
            return output_filename
        else:
            elevenlabs_rotator.remove_key(current_key)

    # Fallback to edge-tts
    print("All ElevenLabs keys exhausted. Falling back to edge-tts...")
    asyncio.run(_generate_fallback_async(text, output_filename))
    return output_filename
