import os
import json
import re
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
    fomo_overlay: str



def _is_topic_duplicate(new_topic: str, used_topics_text: str) -> bool:
    """
    Hard programmatic guard against topic repetition.
    Uses word-level fuzzy matching to catch near-duplicates.
    """
    if not used_topics_text or not new_topic:
        return False

    def normalize(text):
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        return set(text.split())

    STOP_WORDS = {'the', 'a', 'an', 'of', 'and', 'or', 'in', 'on', 'at', 'to',
                  'as', 'is', 'it', 'its', 'be', 'by', 'for', 'with', 'vs', 'effect',
                  'principle', 'theory', 'technique', 'bias', 'syndrome', 'method',
                  'law', 'laws', 'art', 'power', 'human', 'nature'}

    new_words = normalize(new_topic) - STOP_WORDS
    if not new_words:
        return False

    for line in used_topics_text.splitlines():
        line = line.strip().lstrip('- ').strip()
        if not line:
            continue
        old_words = normalize(line) - STOP_WORDS
        if not old_words:
            continue
        overlap = new_words & old_words
        overlap_ratio = len(overlap) / min(len(new_words), len(old_words))
        if overlap_ratio >= 0.6:
            return True

    return False


def generate_content(profile="motivational") -> dict:
    """
    Generates content using Gemini API.
    Behavior changes based on the profile provided.
    """
    history_file = "generated_history.txt"
    if profile == "cartoon":
        history_file = "generated_history_cartoon.txt"
        
    used_topics = ""
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            used_topics = f.read().strip()

    if profile == "cartoon":
        prompt = (
            "You are a scriptwriter for 'Cartoon Plus', a YouTube channel that posts funny Hindi shorts. "
            "Your videos combine calming background footage (like soap cutting or ASMR) with a hilarious, conversational Hindi story or joke. "
            "Write a short, engaging, and very funny Hindi story or joke. It should feel like a casual conversation or a funny anecdote. "
            "DO NOT hardcode exactly 'Ek bar Pintu ne bola...', be creative and come up with your own funny setups and characters (e.g. Pappu, Teacher, Chintu, etc).\n\n"
            
            "SCRIPT STRUCTURE (Strictly follow this):\n"
            "1. THE HOOK: A funny or relatable Hindi opening line to grab attention immediately.\n"
            "2. THE SETUP: Build up the joke or funny scenario.\n"
            "3. THE SUSPENSE CTA: Right before the final punchline (when curiosity is highest), insert a creative, natural call-to-action asking viewers to like the video and subscribe to the channel to hear the end. (e.g. 'Aage kya hua janne se pehle, jaldi se like aur subscribe kardo!'). Vary this naturally.\n"
            "4. THE PUNCHLINE: Deliver the final, hilarious punchline immediately after the CTA.\n\n"
            
            "LANGUAGE RULES:\n"
            "   - Write in conversational Roman Hindi (Hinglish).\n"
            "   - NO markdown: no **, no __, no #. Plain spoken text only.\n"
            "   - Script length: around 50 to 80 words.\n\n"
            
            "PLATFORM SEO METADATA:\n"
            "   - YOUTUBE SHORTS: A clickbaity, funny Hindi title WITH EMOJIS. A description with viral Hindi comedy tags (#funny #comedy #hindi), add more if it can make video viral.\n"
            "   - FACEBOOK/IG REELS: A short funny caption with emojis and hashtags.\n\n"
            
            "VIDEO ASSETS:\n"
            "   - Provide EXACTLY 4 video search keywords to find satisfying/ASMR clips on Pexels. MUST BE ENGLISH.\n"
            "   - Pick ONLY from this proven list (these actually return good results on Pexels):\n"
            "     'soap cutting', 'slime', 'kinetic sand', 'sand art', 'clay cutting',\n"
            "     'water drops', 'sand pouring', 'marble run', 'color powder', 'paint mixing',\n"
            "     'pottery', 'domino', 'bubble wrap', 'satisfying'\n"
            "   - Do NOT invent keywords outside this list.\n"
            "   - One background music keyword: use ONLY one of these: 'quirky', 'playful', 'upbeat'.\n\n"
            
            "OUTPUT FORMAT: Single valid JSON object. NO markdown wrapping.\n"
            "{\n"
            "  \"topic_name\": \"Short description of the joke (for history tracking)\",\n"
            "  \"quote\": \"the full spoken script including the CTA and punchline\",\n"
            "  \"fomo_overlay\": \"Wait for it... 🤣\",\n"
            "  \"video_search_keywords\": [\"soap cutting\", \"satisfying slime\"],\n"
            "  \"music_search_keyword\": \"funny quirky\",\n"
            "  \"yt_title\": \"...\",\n"
            "  \"yt_description\": \"...\",\n"
            "  \"yt_tags\": [\"...\"],\n"
            "  \"fb_caption\": \"...\",\n"
            "  \"fb_hashtags\": \"...\",\n"
            "  \"ig_caption\": \"...\",\n"
            "  \"ig_hashtags\": \"...\"\n"
            "}\n"
        )
    else:
        # Original motivational prompt
        prompt = (
            "You are the scriptwriter for 'NextGenThoughts', one of the fastest-growing psychology channels on YouTube. "
            "Your scripts are inspired by the greatest books ever written on human behavior, power, and dark psychology. "
            "You have deeply studied: '48 Laws of Power', 'The Laws of Human Nature', 'The Art of Seduction', "
            "'The 33 Strategies of War', 'Mastery' by Robert Greene; 'Influence' and 'Pre-Suasion' by Robert Cialdini; "
            "'Thinking, Fast and Slow' by Daniel Kahneman; 'Predictably Irrational' by Dan Ariely; "
            "'The Prince' by Machiavelli; 'Games People Play' by Eric Berne; 'In Sheep's Clothing' by George Simon; "
            "'Never Split the Difference' by Chris Voss; 'The Righteous Mind' by Jonathan Haidt; "
            "'Without Conscience' by Robert Hare; 'The Sociopath Next Door' by Martha Stout; "
            "and 'Why Does He Do That?' by Lundy Bancroft. "
            "Your job is to take a specific law, chapter, or concept from these books and transform it into a short, "
            "electrifying script that feels like a brilliant, passionate teacher is revealing a forbidden life-changing secret. "
            "You do NOT summarize the book. You TELL A STORY. You make the viewer feel something.\n\n"
            
            "SCRIPT STRUCTURE (follow this exact emotional arc):\n"
            "1. THE HOOK (0-3 Seconds) — A highly disruptive, scroll-stopping pattern interrupt. "
            "It must grab them instantly. Do NOT use repetitive hooks. Every video must start differently. "
            "Make it feel urgent, forbidden, or highly relatable. Make them feel seen. 1-2 punchy sentences MAX.\n"
            
            "2. THE REVEAL — Name the psychological concept or law immediately after the hook. "
            "Frame it like a secret: 'That tactic has a name. Robert Greene calls it Law 3: Conceal Your Intentions. "
            "And once you see it, you will spot it everywhere.'\n"
            
            "3. THE TEACHING — This is your masterclass. Explain HOW and WHY this works using a second vivid example. "
            "Write in short, punchy sentences. Vary sentence length for dramatic effect. "
            "Use 'you' and 'your' to speak directly to ONE person. "
            "BANNED phrases: 'cognitive bias', 'research shows', 'studies have found', 'it is important to note', "
            "'this phenomenon', 'in conclusion', 'psychologists say', 'according to'. "
            "Teach it like you are explaining to your smartest friend over coffee.\n"
            
            "4. THE POWER MOVE — End with one actionable, empowering takeaway. "
            "How can they use this or spot it being used on them? "
            "End with a single powerful closing sentence that hits like a punch.\n"
            
            "5. LANGUAGE RULES:\n"
            "   - NO markdown: no **, no __, no #. Plain spoken English only.\n"
            "   - NO special characters or symbols.\n"
            "   - Script length: 100 to 150 words. Every single word must earn its place.\n"
            "   - Read it aloud in your head. If it sounds like a robot or a textbook, rewrite it.\n\n"
            
            "PLATFORM SEO METADATA (generate after the script):\n"
            "   - YOUTUBE SHORTS: A scroll-stopping title WITH EMOJIS (under 80 chars, urgent or forbidden feeling). "
            "A rich, multi-paragraph YouTube description (minimum 150 words). IMPORTANT: You MUST include highly searched phrases "
            "in both English and Romanized Hindi (e.g., 'dark psychology tricks in hindi', 'kaise kare', 'manipulation secrets') organically in the description, ending with hashtags. "
            "A list of 12-15 highly viral, trending tags.\n"
            "   - FACEBOOK REELS: A warm, conversational caption ending with a thought-provoking question. Exactly 7 viral hashtags.\n"
            "   - INSTAGRAM REELS: A short, minimalistic, aesthetic caption. Max 2 lines. 2-3 emojis. 6-8 niche hashtags.\n"
            "   CRITICAL: #NextGenThoughts MUST be the first hashtag on every single platform.\n\n"
            
            "VIDEO ASSETS:\n"
            "   - Provide 5 to 8 hyper-literal Pexels video search keywords. Describe PHYSICAL, VISUAL things, NOT abstract concepts.\n"
            "   - BAN abstract words: 'psychology', 'mindset', 'success', 'manipulation', 'power', 'sadness'.\n"
            "   - INSTEAD: 'person walking dark room', 'eye close up macro', 'chess pieces hand', 'two people arguing office'.\n"
            "   - One background music keyword: calm and ambient ONLY (e.g., 'calm piano', 'cinematic ambient', 'lo-fi focus').\n\n"
            
            "OUTPUT FORMAT: Single valid JSON object. NO markdown wrapping.\n"
            "The 'topic_name' must be: [Book Title] — [Specific Law/Concept Name]. "
            "Example: '48 Laws of Power — Law 3: Conceal Your Intentions'\n"
            "The 'fomo_overlay' is a short, clickbaity half-caption that stays on screen (e.g. 'The real reason they ignore you...'). Max 7 words.\n"
            "{\n"
            "  \"topic_name\": \"...\",\n"
            "  \"quote\": \"the full spoken script\",\n"
            "  \"fomo_overlay\": \"...\",\n"
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

    if profile == "cartoon":
        # For cartoon, just append the already-used joke topics to avoid repeats
        prompt += (
            "\n--- JOKES ALREADY USED (DO NOT REPEAT THESE SETUPS OR PUNCHLINES) ---\n"
            + (used_topics if used_topics else "(none yet — be creative!)")
            + "\n----------------------------------------------\n"
            "Now generate a completely fresh, original funny Hindi short script.\n"
        )
    else:
        # ── Master Book + Psychology Topic Universe (motivational only) ──────────
        MASTER_TOPIC_LIST = """
=== 48 Laws of Power (Robert Greene) ===
Law 1: Never Outshine the Master | Law 2: Never Put Too Much Trust in Friends | Law 3: Conceal Your Intentions
Law 4: Always Say Less Than Necessary | Law 6: Court Attention at All Cost | Law 7: Get Others to Do the Work
Law 9: Win Through Your Actions, Never Through Argument | Law 11: Learn to Keep People Dependent on You
Law 12: Use Selective Honesty to Disarm Your Victim | Law 15: Crush Your Enemy Totally
Law 16: Use Absence to Increase Respect | Law 17: Keep Others in Suspended Terror
Law 18: Do Not Build Fortresses | Law 19: Know Who You Are Dealing With | Law 20: Do Not Commit to Anyone
Law 21: Play a Sucker to Catch a Sucker | Law 22: Use the Surrender Tactic | Law 25: Re-Create Yourself
Law 26: Keep Your Hands Clean | Law 27: Play on People's Need to Believe | Law 28: Enter Action with Boldness
Law 29: Plan All the Way to the End | Law 31: Control the Options | Law 32: Play to People's Fantasies
Law 33: Discover Each Man's Thumbscrew | Law 34: Be Royal in Your Own Fashion | Law 38: Think as You Like, But Behave Like Others
Law 43: Work on the Hearts and Minds of Others | Law 44: Disarm and Infuriate with the Mirror Effect
Law 45: Preach the Need for Change, But Never Reform Too Much | Law 48: Assume Formlessness

=== The Laws of Human Nature (Robert Greene) ===
Law 1: Master Your Emotional Self | Law 2: Transform Self-Love into Empathy | Law 3: See Through People's Masks
Law 4: Determine the Strength of People's Character | Law 5: Become an Elusive Object of Desire
Law 6: Elevate Your Perspective | Law 7: Soften People's Resistance by Confirming Their Self-Opinion
Law 8: Change Your Circumstances by Changing Your Attitude | Law 9: Confront Your Dark Side
Law 10: Beware the Fragile Ego | Law 11: Know Your Limits | Law 12: Reconnect to the Masculine or Feminine Within You
Law 13: Advance With a Sense of Purpose | Law 14: Resist the Downward Pull of the Group
Law 15: Make Them Want to Follow You | Law 16: See the Hostility Behind the Friendly Facade
Law 17: Seize the Historical Moment | Law 18: Meditate on Our Common Mortality

=== Influence (Robert Cialdini) ===
Cialdini: Reciprocity as Weapon | Cialdini: Commitment and Consistency Trap | Cialdini: Social Proof Manipulation
Cialdini: Authority Illusion | Cialdini: Liking and the Halo Effect | Cialdini: Scarcity and FOMO
Cialdini: Unity — The We Principle | Pre-Suasion: Channeling Attention Before the Ask

=== The Art of Seduction (Robert Greene) ===
Seduction: The Siren | Seduction: The Rake | Seduction: The Ideal Lover | Seduction: The Dandy
Seduction: The Natural | Seduction: The Coquette | Seduction: The Charmer | Seduction: The Charismatic
Seduction: Creating Mystery and Lure | Seduction: Sending Mixed Signals | Seduction: Appear to Be an Object of Desire
Seduction: The Isolation Tactic | Seduction: Spiritual Lure

=== Thinking Fast and Slow (Kahneman) ===
System 1 vs System 2 Thinking | The Availability Heuristic | Anchoring Effect | Overconfidence Illusion
The Halo Effect | What You See Is All There Is (WYSIATI) | Loss Aversion | Endowment Effect | Framing Decisions

=== Other Landmark Books ===
Machiavelli: The Prince — It Is Better to Be Feared Than Loved | Machiavelli: Ends Justify the Means
Games People Play (Berne): The Victim-Rescuer-Persecutor Triangle | Berne: "Yes But" Game | Berne: "Kick Me" Game
In Sheep's Clothing (Simon): Covert Aggression | Simon: Guilt-Tripping as Control | Simon: Minimizing and Denying
Never Split the Difference (Voss): Tactical Empathy | Voss: Mirroring in Negotiation | Voss: Calibrated Questions
The Sociopath Next Door: Conscience-Free Predators | Without Conscience (Hare): The Psychopathy Checklist
Predictably Irrational (Ariely): The Zero Price Effect | Ariely: The Power of Free | Ariely: Relativity Trap
Why Does He Do That (Bancroft): Abuser Mentality | Bancroft: The Entitlement Mindset

=== Dark Psychology Concepts (No Specific Book) ===
Dark Triad Traits | Narcissistic Abuse Cycle | Gaslighting Tactics | Love Bombing | Intermittent Reinforcement
Trauma Bonding | DARVO Technique | Flying Monkeys | Hoovering | Future Faking | Triangulation
Bystander Effect | Mob Mentality | Sunk Cost Fallacy | The Backfire Effect | Zeigarnik Effect
Learned Helplessness | Emotional Blackmail | Stockholm Syndrome | Fawn Response | Gray Rock Method
Dunning-Kruger Effect | Impostor Syndrome | Negativity Bias | Pratfall Effect | Hedonic Adaptation
Reactance Theory | Forbidden Fruit Effect | The Ben Franklin Effect | Decision Fatigue | Ego Depletion
Breadcrumbing | Push-Pull Dynamic | Anxious Attachment | Parasocial Relationships | Pity Plays
"""

        prompt += (
            "\n--- MASTER CONTENT LIBRARY (your primary source material) ---\n"
            f"{MASTER_TOPIC_LIST}\n"
            "\n--- TOPICS ALREADY USED (NEVER REPEAT OR CLOSELY OVERLAP THESE) ---\n"
            + (used_topics if used_topics else "(none yet — you're free to start anywhere)")
            + "\n----------------------------------------------\n"
            "Your task: FIRST scan the master library above for any unused topic. "
            "Strongly prefer specific BOOK LAWS (e.g., '48 Laws of Power — Law 3') over generic psychology concepts — "
            "they make the most compelling, unique content. "
            "Pick the most surprising, counterintuitive, or rarely-discussed unused entry. "
            "If ALL entries in the library have been used, invent a new niche dark psychology concept with the same depth. "
            "The topic_name MUST follow the format: '[Book Title] — [Law/Concept]' for book-based topics. "
            "Now generate a completely fresh, original script."
        )

    max_retries = 5
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

            start_idx = raw_text.find('{')
            end_idx = raw_text.rfind('}')

            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                raw_text = raw_text[start_idx:end_idx+1]
            else:
                raise json.JSONDecodeError("No JSON object could be found in the response.", raw_text, 0)

            content = json.loads(raw_text.strip())

            topic_name = content.get('topic_name', content.get('quote', '')[:60])

            # ── HARD DUPLICATE GUARD ──────────────────────────────────────────────
            # Programmatically reject duplicates — never trust Gemini alone.
            if _is_topic_duplicate(topic_name, used_topics):
                print(f"⚠️  Duplicate topic detected ('{topic_name}'). Forcing retry...")
                max_retries += 1  # Don't waste a retry on Gemini's mistake
                continue
            # ─────────────────────────────────────────────────────────────────────

            # Save ONLY the topic name to history — not the full script.
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(f"- {topic_name}\n")

            print(f"✅ Fresh topic selected: '{topic_name}'")
            return content

        except errors.APIError as e:
            print(f"Gemini API Error with key {current_key[:5]}...: {e}")
            if e.code in [429, 403]:
                print(f"Key {current_key[:5]}... hit limit. Rotating...")
                gemini_rotator.remove_key(current_key)
            else:
                print("Unknown API error, rotating key anyway.")
                gemini_rotator.remove_key(current_key)
        except json.JSONDecodeError:
            print("Failed to decode JSON from Gemini response. Raw output was:")
            print(raw_text)
            print("Retrying generation...")
            continue
        except Exception as e:
            print(f"Unexpected error: {e}")
            gemini_rotator.remove_key(current_key)

    print("All Gemini API keys exhausted.")
    return {}

if __name__ == "__main__":
    print(generate_content())
