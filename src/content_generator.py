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
    # The history file stores ONLY the topic names, not full scripts.
    # This keeps the forbidden list clean and scannable for Gemini.
    history_file = "generated_history.txt"
    used_topics = ""
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            used_topics = f.read().strip()

    prompt = (
        "You are the scriptwriter for 'NextGenThoughts', one of the fastest-growing psychology channels on YouTube. "
        "Your job is to write a script that feels like a brilliant, passionate teacher is sitting across from the viewer and revealing a life-changing secret. "
        "You do NOT present facts. You TELL STORIES. You make the viewer feel something. "
        "Think of the best teacher you ever had — the one who made you lean forward, forget to check your phone, and feel genuinely smarter after the lesson. That is your voice.\n\n"

        "SCRIPT STRUCTURE (follow this exact emotional arc):\n"
        "1. THE HOOK — A vivid, relatable real-life scenario (NOT a question like 'Have you ever...'). "
        "Drop the viewer into a moment. Example: 'You walk into a room full of strangers. Five minutes later, one person already feels like an old friend. You have no idea why.' "
        "Make it feel personal. Make them feel seen. 2-3 sentences MAX.\n"

        "2. THE REVEAL — Name the psychological concept immediately after the hook. "
        "Frame it like a secret: 'That feeling has a name. Scientists call it the Mere Exposure Effect. And once you understand it, you will never see social situations the same way again.'\n"

        "3. THE TEACHING — This is your masterclass. Explain HOW and WHY this works using a second vivid, relatable real-world example. "
        "Write in short, punchy sentences with rhythm. Vary sentence length for dramatic effect. "
        "Use 'you' and 'your' to speak directly to ONE person. "
        "BANNED phrases (NEVER use these): 'cognitive bias', 'research shows', 'studies have found', 'it is important to note', 'this phenomenon', 'in conclusion', 'psychologists say'. "
        "Teach it like you are explaining to your smartest friend over coffee.\n"

        "4. THE POWER MOVE — End with one actionable, empowering takeaway. "
        "How can they use this or spot it being used on them? Make the viewer feel like they just unlocked a cheat code for life. "
        "End with a single powerful closing sentence that hits like a punch. Example: 'Familiarity is not love. But your brain cannot tell the difference.'\n"

        "5. LANGUAGE RULES:\n"
        "   - NO markdown: no **, no __, no #. Plain spoken English only.\n"
        "   - NO special characters or symbols.\n"
        "   - Script length: 100 to 150 words. Every single word must earn its place.\n"
        "   - Read it aloud in your head. If it sounds like a robot or a textbook, rewrite it.\n\n"

        "PLATFORM SEO METADATA (generate after the script):\n"
        "   - YOUTUBE SHORTS: A scroll-stopping title WITH EMOJIS (under 80 chars, make it feel urgent or forbidden). "
        "A rich, multi-paragraph YouTube description that expands on the concept with more depth (minimum 150 words), ending with hashtags. "
        "A list of 12-15 highly viral, trending tags.\n"
        "   - FACEBOOK REELS: A warm, conversational caption that ends with a thought-provoking question to drive comments. Exactly 7 viral hashtags.\n"
        "   - INSTAGRAM REELS: A short, minimalistic, aesthetic caption. Max 2 lines. 2-3 emojis. 6-8 niche hashtags.\n"
        "   CRITICAL: #NextGenThoughts MUST be the first hashtag on every single platform.\n\n"

        "VIDEO ASSETS:\n"
        "   - Provide 5 to 8 hyper-literal Pexels video search keywords. You MUST describe physical, visual things, NOT abstract concepts.\n"
        "   - BAN abstract words: Do NOT use words like 'psychology', 'mindset', 'success', 'manipulation', 'sadness'.\n"
        "   - INSTEAD use literal descriptions: If the script says 'You walk into a dark room', the keyword MUST be 'person walking dark room'. If it says 'Your brain', use 'eye close up macro' or 'silhouette person'.\n"
        "   - Provide one background music keyword. It MUST be calm and ambient (e.g., 'calm piano', 'cinematic ambient', 'lo-fi focus'). "
        "NEVER suggest intense, loud, or dramatic music.\n\n"

        "OUTPUT FORMAT: Your ENTIRE response must be a single valid JSON object with this exact structure. "
        "The 'topic_name' must be a short 3-7 word title for the psychological concept (e.g. 'Foot-in-the-Door Technique'). "
        "DO NOT wrap it in markdown or code blocks:\n"
        "{\n"
        "  \"topic_name\": \"...\",\n"
        "  \"quote\": \"the full spoken script\",\n"
        "  \"video_search_keywords\": [\"keyword1\", \"keyword2\"],\n"
        "  \"music_search_keyword\": \"...\",\n"
        "  \"yt_title\": \"...\",\n"
        "  \"yt_description\": \"...\",\n"
        "  \"yt_tags\": [\"...\"],\n"
        "  \"fb_caption\": \"...\",\n"
        "  \"fb_hashtags\": \"...\",\n"
        "  \"ig_caption\": \"...\",\n"
        "  \"ig_hashtags\": \"...\"\n"
        "}\n"
    )

    # ── Master Topic Universe ──────────────────────────────────────────────────
    # A curated list of 80+ dark psychology, behavioral science, and persuasion
    # topics. Gemini MUST pick from this list — never default to the most famous ones.
    MASTER_TOPIC_LIST = """
Dark Triad Traits | Narcissistic Abuse Cycle | Gaslighting Tactics | Love Bombing | Intermittent Reinforcement
Trauma Bonding | Coercive Control | DARVO Technique | Silent Treatment as Punishment | Isolation Tactics
Future Faking | Triangulation (jealousy tactic) | Flying Monkeys (social manipulation) | Smear Campaigns | Hoovering
Bystander Effect | Diffusion of Responsibility | Mob Mentality / Deindividuation | Authority Bias | Milgram Obedience Experiments
Stanford Prison Experiment Lessons | Conformity (Asch Line Experiments) | Social Proof as Manipulation | Fear of Ostracism | Social Exclusion Pain
Sunk Cost Fallacy | Escalation of Commitment | Cognitive Dissonance (advanced) | Belief Perseverance | The Backfire Effect
Choice Architecture | Nudge Theory | Default Effect | Status Quo Bias | IKEA Effect
Framing Effect | Anchoring Bias | Decoy Effect | Contrast Effect | Peak-End Rule
Narrative Transportation Theory | The Zeigarnik Effect (unfinished tasks) | Mere Exposure Effect | Propinquity Effect | Parasocial Relationships
Emotional Contagion | Mirror Neuron Manipulation | Limbic Resonance | Pity Plays | Weaponized Vulnerability
Victim Mentality as Control | Learned Helplessness | Emotional Blackmail | Stockholm Syndrome | Fawn Response
Scapegoating | Projection (psychological) | Blame-Shifting | The JADE Trap (Justify Argue Defend Explain) | Gray Rock Method
False Memory Implantation | Hindsight Bias | Illusory Superiority (Lake Wobegon Effect) | Dunning-Kruger Effect | Impostor Syndrome
Self-Serving Bias | Fundamental Attribution Error | Just-World Hypothesis | Optimism Bias | Negativity Bias
The Pratfall Effect | Paradox of Choice | Decision Fatigue | Ego Depletion | Hedonic Adaptation
Reactance Theory | Forbidden Fruit Effect | Boomerang Effect | Reverse Psychology | The Ben Franklin Effect
Rational Emotive Behavior | Cognitive Reframing | Thought-Stopping Technique | Mental Contrasting (WOOP) | Implementation Intentions
Ambiguity Effect | Availability Heuristic | Representativeness Heuristic | Base Rate Neglect | Planning Fallacy
Impression Management | Self-Handicapping | Self-Monitoring | Strategic Self-Presentation | Humblebrag Manipulation
Secure vs Anxious vs Avoidant Attachment | Anxious Attachment Triggers | Fear of Abandonment | Push-Pull Dynamic | Breadcrumbing
"""

    prompt += (
        "\n--- MASTER TOPIC LIST (pick ONLY from here) ---\n"
        f"{MASTER_TOPIC_LIST}\n"
        "\n--- TOPICS ALREADY USED (NEVER REPEAT OR CLOSELY OVERLAP THESE) ---\n"
        + (used_topics if used_topics else "(none yet — you're free to start anywhere)")
        + "\n----------------------------------------------\n"
        "Your task: Pick ONE unused topic from the master list above. "
        "Do NOT pick the most obvious or popular one. Explore the unusual, the surprising, and the counterintuitive corners of the list. "
        "Now generate a completely fresh, original script on your chosen topic."
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
            
            # Find the first '{' and the last '}' to handle any text output before/after the JSON
            start_idx = raw_text.find('{')
            end_idx = raw_text.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                raw_text = raw_text[start_idx:end_idx+1]
            else:
                raise json.JSONDecodeError("No JSON object could be found in the response.", raw_text, 0)
                
            # Parse the JSON response
            content = json.loads(raw_text.strip())
            
            # Save ONLY the topic name to history — not the full script.
            # This keeps the anti-repetition list clean and readable for Gemini.
            topic_name = content.get('topic_name', content.get('quote', '')[:60])
            with open(history_file, "a", encoding="utf-8") as f:
                    f.write(f"- {topic_name}\n")
                    
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
