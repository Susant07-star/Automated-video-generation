import os
import json
import time
from google import genai
from google.genai import errors
from pydantic import BaseModel
from src.api_manager import gemini_rotator

class ContentResponse(BaseModel):
    quote: str
    video_search_keyword: str
    music_search_keyword: str
    caption: str
    hashtags: str

def generate_content() -> dict:
    """
    Generates a motivational quote, search keywords, caption, and hashtags using Gemini API.
    Returns a dictionary with the generated content.
    """
    prompt = (
        "You are a top-tier short-form video scriptwriter for a motivational channel called NextGenThoughts. "
        "Write a spoken script for a 30-50 second motivational reel. "
        "Rules:\n"
        "1. Start with a UNIQUE, punchy hook — never use 'Here is your motivation' or 'Today's quote'. "
        "   Use varied openers like 'Stop waiting.', 'Nobody tells you this.', 'The truth is...', "
        "   'Most people quit right before...', 'One decision changes everything.' etc.\n"
        "2. Build with 3-4 short, punchy sentences. Use pauses naturally (commas, short sentences).\n"
        "3. End with a powerful call to action — but vary it each time. "
        "   Example endings: 'Now go do the work.', 'Are you going to act today?', "
        "   'The clock is ticking.', 'Your future self is watching.' etc.\n"
        "4. Total script: 35-55 words. Written to be SPOKEN aloud, not read.\n"
        "5. Tone: direct, powerful, emotional — like a coach speaking face to face.\n"
        "Also provide: a single Pexels video search keyword, a single Pixabay music keyword, "
        "an engaging Facebook caption, and relevant hashtags."
    )

    while gemini_rotator.has_keys():
        current_key = gemini_rotator.get_random_key()
        try:
            client = genai.Client(api_key=current_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config={
                    'response_mime_type': 'application/json',
                    'response_schema': ContentResponse,
                }
            )
            # Parse the JSON response
            content = json.loads(response.text)
            return content
            
        except errors.APIError as e:
            print(f"Gemini API Error with key {current_key[:5]}...: {e}")
            # If rate limited (429) or quota exceeded, remove the key and try again
            if e.code in [429, 403]:
                print(f"Key {current_key[:5]}... hit limit. Rotating...")
                gemini_rotator.remove_key(current_key)
            else:
                # Some other error, maybe still rotate or fail
                print("Unknown API error, rotating key anyway.")
                gemini_rotator.remove_key(current_key)
        except json.JSONDecodeError:
            print("Failed to decode JSON from Gemini response.")
            return {}
        except Exception as e:
            print(f"Unexpected error: {e}")
            gemini_rotator.remove_key(current_key)
            
    print("All Gemini API keys exhausted.")
    return {}

if __name__ == "__main__":
    print(generate_content())
