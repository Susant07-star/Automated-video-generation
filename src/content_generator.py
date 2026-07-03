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
        "Generate a short, powerful motivational quote (around 15-25 words) suitable for a short Facebook Reel. "
        "Also provide a single search keyword to find a background video on Pexels (e.g., 'nature', 'city', 'workout', 'success'). "
        "Provide a single search keyword to find background music on Pixabay (e.g., 'cinematic', 'lofi', 'epic'). "
        "Provide an engaging caption for the Facebook post. "
        "Finally, provide a string of relevant hashtags separated by spaces (e.g., '#motivation #success')."
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
