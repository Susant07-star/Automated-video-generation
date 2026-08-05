import os
import requests
import base64
from dotenv import load_dotenv

load_dotenv()

VOICE_ID = "qeVMjfAnyqoR0DeCeeXL"
TEXT = """
In the realm of dark psychology, the silent treatment is one of the most powerful manipulation tactics. It is designed to completely strip you of your power by making you feel invisible. When someone suddenly withdraws their attention and refuses to communicate, they are deliberately creating an emotional vacuum. This vacuum forces you to overthink, question your own reality, and desperately seek their validation just to restore a sense of normalcy. The silent treatment isn't about avoiding conflict; it's about establishing absolute control. By denying you closure, they keep you anchored to them in a state of constant anxiety. The most effective counter-tactic? Recognize the silence for what it is: a game of emotional dominance. Instead of begging for answers, match their silence with your own absolute indifference. When they realize their absence no longer destabilizes you, their weapon instantly loses its edge. True power lies in your ability to remain completely unaffected.
"""

def generate_reference():
    raw_keys = os.getenv("ELEVENLABS_API_KEYS", "")
    keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
    
    if not keys:
        print("No ElevenLabs API keys found.")
        return
        
    for key in keys:
        print(f"Trying key ending in {key[-4:]}...")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
        headers = {
            "Content-Type": "application/json",
            "xi-api-key": key
        }
        data = {
            "text": TEXT.strip(),
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.30,
                "similarity_boost": 0.75,
                "style": 0.70,
                "use_speaker_boost": True
            }
        }
        
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            audio_data = response.content
            with open("reference_voice.mp3", "wb") as f:
                f.write(audio_data)
            print("Successfully generated reference_voice.mp3")
            return
        else:
            print(f"Failed with key {key[-4:]}: {response.text}")

    print("All keys failed to generate reference voice. (None had access to the voice ID)")

if __name__ == "__main__":
    generate_reference()
