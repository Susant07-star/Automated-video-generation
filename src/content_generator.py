import os
import json
import time
from google import genai
from google.genai import errors
from pydantic import BaseModel
from src.api_manager import gemini_rotator

class ContentResponse(BaseModel):
    quote: str
    video_search_keywords: list[str]
    music_search_keyword: str
    caption: str
    hashtags: str

def generate_content() -> dict:
    """
    Generates a motivational quote, search keywords, caption, and hashtags using Gemini API.
    Maintains a history of past generations to utilize the large context window and avoid repetition.
    Returns a dictionary with the generated content.
    """
    history_file = "generated_history.txt"
    history_context = ""
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            history_context = f.read()

    prompt = (
        "You are a top-tier educational YouTube Shorts/Reels scriptwriter for a viral channel called NextGenThoughts. "
        "The channel focuses on TEACHING deep psychology, human behavior, and manipulation tactics clearly and engagingly. "
        "Write a spoken script for a highly engaging, long-form short (40-70 seconds). "
        "Rules:\n"
        "1. THE HOOK: Start with a mind-blowing question or fact to hook the viewer (e.g., 'Have you ever noticed why you instantly trust someone who mimics your body language?').\n"
        "2. THE CONCEPT: Clearly name the actual psychological principle (e.g., The Chameleon Effect, The Pygmalion Effect).\n"
        "   Use your search grounding tool to pull REAL psychological facts, but EXPLAIN IT SIMPLY. DO NOT include boring academic data, dates, or names of researchers (e.g., avoid 'A 1975 study by...'). Just teach the core concept in a highly engaging, easy-to-understand way.\n"
        "3. THE EXPLANATION: Teach the audience *how* and *why* this works. Break it down simply, like a charismatic YouTuber explaining a concept to a friend. Keep it punchy, conversational, and intense.\n"
        "4. THE DEFENSE/APPLICATION: Explain how the viewer can spot this being used against them in daily life, or how they can use it ethically.\n"
        "5. LENGTH & PACING: The script MUST be between 70 and 130 words long. It should feel like a mini-documentary or a high-value explainer video, NOT just a short edgy quote.\n"
        "7. PLATFORM-SPECIFIC SEO METADATA: You must generate perfectly optimized metadata for three different platforms:\n"
        "   - YOUTUBE SHORTS: Provide a highly clickable title (under 80 chars), a rich description, and a list of 5-8 SEO tags.\n"
        "   - FACEBOOK REELS: Provide a conversational caption with a thought-provoking question to drive comments, and exactly 7 highly viral hashtags.\n"
        "   - INSTAGRAM REELS: Provide a highly aesthetic, minimalistic caption with 2-3 emojis, and 5-7 deeply targeted niche hashtags (e.g., #DarkPsychology, #Mindset).\n"
        "   **CRITICAL:** You MUST include #NextGenThoughts as the first hashtag on every platform.\n"
        "8. VIDEO ASSETS: Because this is a longer script, provide a randomized number of distinct Pexels video search keywords (between 4 and 8 keywords, spaced out to match the topics in the script). "
        "Also provide a single background music keyword. **CRITICAL:** The music keyword MUST be for clean, ambient, cinematic, or calm lo-fi music (e.g., 'ambient piano', 'cinematic calm', 'deep focus'). DO NOT request noisy, intense, or loud music like 'urgent tension' or 'heavy beats', as it ruins the voiceover.\n\n"
        "IMPORTANT: Your ENTIRE response MUST be valid JSON matching this exact structure:\n"
        "{\n"
        "  \"quote\": \"...\",\n"
        "  \"video_search_keywords\": [\"...\"],\n"
        "  \"music_search_keyword\": \"...\",\n"
        "  \"yt_title\": \"...\",\n"
        "  \"yt_description\": \"...\",\n"
        "  \"yt_tags\": [\"...\"],\n"
        "  \"fb_caption\": \"...\",\n"
        "  \"fb_hashtags\": \"...\",\n"
        "  \"ig_caption\": \"...\",\n"
        "  \"ig_hashtags\": \"...\"\n"
        "}\n"
        "Do NOT wrap the response in markdown blocks like ```json."
    )
    
    if history_context:
        prompt += (
            "--- PAST GENERATED SCRIPTS (CRITICAL: DO NOT REPEAT THESE TOPICS OR CONCEPTS) ---\n"
            f"{history_context}\n"
            "----------------------------------------------------------------------------------\n"
            "Now, generate a completely NEW script covering a different dark psychology or human behavior concept."
        )

    max_retries = 3
    while gemini_rotator.has_keys() and max_retries > 0:
        max_retries -= 1
        current_key = gemini_rotator.get_random_key()
        try:
            client = genai.Client(api_key=current_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config={
                    'tools': [{'google_search': {}}],
                }
            )
            
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
                
            # Parse the JSON response
            content = json.loads(raw_text.strip())
            
            # Save the new quote to history to leverage the massive context window next time
            if "quote" in content:
                with open(history_file, "a", encoding="utf-8") as f:
                    f.write(f"- {content['quote']}\n")
                    
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
            print("Failed to decode JSON from Gemini response. Raw output was:")
            print(raw_text)
            print("Retrying generation...")
            # We don't remove the key since it's a prompt/model issue, not an auth issue
            continue
        except Exception as e:
            print(f"Unexpected error: {e}")
            gemini_rotator.remove_key(current_key)
            
    print("All Gemini API keys exhausted.")
    return {}

if __name__ == "__main__":
    print(generate_content())
