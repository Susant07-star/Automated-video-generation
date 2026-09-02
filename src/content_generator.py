import os
import json
import re
import time
import datetime
from google.genai import errors
from pydantic import BaseModel
from src.api_manager import create_gemini_client, gemini_rotator, is_gemini_model_overloaded, is_gemini_timeout

class ContentResponse(BaseModel):
    quote: str
    video_search_keywords: list[str]
    music_search_keyword: str
    caption: str
    hashtags: str
    fomo_overlay: str


DEFAULT_RESEARCH_MODELS = [
    'gemini-2.5-flash-lite',
    'gemini-3.1-flash-lite',
    'gemini-3.5-flash-lite',
    'gemini-2.5-flash',
    'gemini-3.5-flash',
]

DEFAULT_WRITER_MODELS = [
    'gemini-3.7-flash',
    'gemini-3.6-flash',
    'gemini-3.5-flash',
    'gemini-3-flash-preview',
    'gemini-3.5-flash-lite',
    'gemini-3.1-flash-lite',
    'gemini-2.5-flash-lite',
    'gemini-2.5-flash',
]


def _env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_list(name: str, default: list[str]) -> list[str]:
    raw_value = os.getenv(name, "")
    values = [item.strip() for item in raw_value.split(",") if item.strip()]
    return values or default


def _profile_model_list(profile: str, profile_env: str, shared_env: str, default: list[str]) -> list[str]:
    if profile == "cartoon":
        profile_models = _env_list(profile_env, [])
        if profile_models:
            return profile_models
    return _env_list(shared_env, default)


def _gemini_search_config() -> dict:
    return {"tools": [{"google_search": {}}]}


def _extract_json_text(raw_text: str) -> str:
    start_idx = raw_text.find('{')
    end_idx = raw_text.rfind('}')
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        return raw_text.strip()

    json_text = raw_text[start_idx:end_idx + 1].strip()
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        return raw_text.strip()
    return json.dumps(parsed, ensure_ascii=False, indent=2)


def _research_brief_path(profile: str) -> str:
    return "latest_research_brief_cartoon.json" if profile == "cartoon" else "latest_research_brief.json"


def _save_research_brief(profile: str, research_brief: str) -> dict:
    try:
        brief = json.loads(research_brief)
    except json.JSONDecodeError:
        brief = {"raw_brief": research_brief}

    payload = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "profile": profile,
        "brief": brief,
    }

    with open(_research_brief_path(profile), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return payload


def _call_gemini_text_with_fallback(
    *,
    contents: str,
    models_to_try: list[str],
    use_search: bool,
    purpose: str,
) -> str:
    config = _gemini_search_config() if use_search else None

    for model_name in models_to_try:
        keys_to_try = gemini_rotator.get_all_keys()
        if not keys_to_try:
            print(f"All Gemini API keys exhausted while running {purpose}.")
            break

        search_label = " with Google Search" if use_search else ""
        print(f"\n📡 {purpose}: trying '{model_name}'{search_label} across {len(keys_to_try)} key(s)...")

        skip_model = False
        for current_key in keys_to_try:
            if not gemini_rotator.has_keys():
                break

            client = create_gemini_client(current_key)
            request_kwargs = {
                "model": model_name,
                "contents": contents,
            }
            if config:
                request_kwargs["config"] = config

            try:
                print(f"  Trying key {current_key[:8]}...")
                response = client.models.generate_content(**request_kwargs)
                print(f"  ✅ {purpose} succeeded with '{model_name}'")
                return _extract_json_text(response.text.strip())
            except errors.APIError as e:
                print(f"  Gemini API Error — {purpose}, model '{model_name}', key {current_key[:8]}...: {e}")
                code = getattr(e, 'code', None)
                if is_gemini_model_overloaded(e):
                    print("  ↳ 503/504 backend timeout or high demand. Skipping this model tier instead of trying more keys...")
                    skip_model = True
                    break
                if code == 429:
                    error_str = str(e).lower()
                    if "quota" in error_str or "exhausted" in error_str:
                        print("  ↳ 429 quota exhausted. Moving to next key...")
                    else:
                        print("  ↳ 429 rate limit. Sleeping 3s, then trying next key...")
                        time.sleep(3)
                    continue
                if code == 403:
                    if use_search:
                        print("  ↳ 403 Forbidden for this Search call. Keeping key available for writer models...")
                    else:
                        print("  ↳ 403 Forbidden (invalid or unauthorized key). Removing key globally...")
                        gemini_rotator.remove_key(current_key)
                    continue
                if code in (404, 400):
                    print(f"  ↳ Model error ({code}). Moving to next model tier...")
                    skip_model = True
                    break

                print(f"  ↳ Other API error ({code}). Moving to next key...")
            except Exception as e:
                if is_gemini_timeout(e):
                    print(f"  ↳ Gemini request timed out during {purpose}. Skipping '{model_name}' and falling back...")
                    skip_model = True
                    break
                print(f"  Unexpected error during {purpose}: {e}")

        if skip_model:
            continue
        print(f"  ⚠️  {purpose}: model '{model_name}' exhausted. Falling back...")

    return ""


def _build_research_prompt(profile: str, used_topics: str, master_topic_list: str = "") -> str:
    used_block = used_topics if used_topics else "(none yet)"

    if profile == "cartoon":
        return f"""
You are a YouTube Shorts researcher for a Hindi comedy channel named Cartoon Plus.
Use Google Search to create a compact creative research brief for one new short.

SEARCH GOALS:
1. Find current Hindi comedy Shorts/Reels language patterns, joke setups, and relatable everyday situations.
2. Find what short-form Hindi comedy audiences are reacting to recently.
3. Find satisfying/ASMR background formats that pair well with comedy shorts.

ALREADY USED JOKES/TOPICS:
{used_block}

OUTPUT RAW JSON ONLY:
{{
  "search_queries_used": ["..."],
  "fresh_joke_angles": [
    {{
      "topic_name": "short unique joke topic",
      "setup": "one-line setup",
      "conflict": "what creates curiosity",
      "punchline_direction": "not the exact punchline, just the direction",
      "audience_trigger": "why viewers would watch"
    }}
  ],
  "language_notes": ["current Hinglish/Hindi phrasing ideas"],
  "metadata_keywords": ["high-intent searchable phrases"],
  "visual_pairing_notes": ["satisfying/ASMR visuals that fit"]
}}

Rules:
- Do not copy jokes from the web.
- Do not repeat any used topic.
- Use research only to discover patterns, situations, phrasing, and audience demand.
- Keep it concise.
"""

    return f"""
You are the research producer for NextGenThoughts, a psychology and dark-human-behavior YouTube Shorts channel.
Use Google Search to create a compact creator brief for one new short.

SEARCH GOALS:
1. Start from the master topic library when possible. Pick an unused topic with strong emotional stakes.
2. Use Google Search to deepen that topic with reputable sources: book summaries, author interviews, lecture notes, evergreen explainers, psychology/negotiation/persuasion articles, or credible educational pages.
3. Use Google Search to capture current audience language: manipulation, narcissism, confidence, influence, toxic relationships, power, discipline, attraction, negotiation, status, betrayal, fear, attention, and Romanized Hindi discovery phrases.
4. Find one vivid real-world situation that makes the idea feel lived-in instead of academic.
5. If the master library is exhausted or too repetitive, propose a genuinely new adjacent concept with the same bookish, high-status feel.

MASTER TOPIC LIBRARY:
{master_topic_list or "(no master library provided)"}

ALREADY USED TOPICS:
{used_block}

OUTPUT RAW JSON ONLY:
{{
  "search_queries_used": ["..."],
  "recommended_topic": {{
    "topic_name": "Book or field - specific concept",
    "topic_source": "master_library or web_expansion",
    "source_basis": "where the idea comes from, in plain words",
    "fresh_angle": "the unexpected angle for Shorts",
    "audience_pain": "viewer problem or fear this connects to",
    "story_scenario": "concrete scene for the script",
    "power_move": "actionable takeaway",
    "metadata_keywords": ["searchable phrase", "romanized hindi phrase"]
  }},
  "backup_topics": [
    {{
      "topic_name": "Book or field - specific concept",
      "fresh_angle": "the unexpected angle for Shorts",
      "reason_to_keep": "why this could become a future short"
    }}
  ],
  "hook_patterns": [
    {{
      "pattern": "specific hook structure",
      "example": "original hook example, not copied from the web",
      "psychological_trigger": "curiosity/fear/identity threat/social danger/forbidden knowledge"
    }}
  ],
  "retention_ladder": ["beat 1", "beat 2", "beat 3", "beat 4"],
  "title_and_seo_notes": ["phrases and title patterns worth using"],
  "visual_metaphors": ["literal Pexels-searchable scenes"],
  "avoid": ["topics or angles to avoid because they are overused or already used"]
}}

Rules:
- Do not quote copyrighted books.
- Use sources for inspiration, terminology, and audience demand, then synthesize an original angle.
- Do not repeat or closely overlap the used topics.
- Prefer a master-library topic unless research strongly shows a better unused web-expansion topic.
- Keep it concise and useful to the scriptwriter.
"""


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


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text or ""))


def _content_quality_errors(content: dict, profile: str) -> list[str]:
    errors_found: list[str] = []
    quote = content.get("quote", "")
    topic_name = content.get("topic_name", "")
    video_keywords = content.get("video_search_keywords", [])
    fomo_overlay = content.get("fomo_overlay", "")

    if not topic_name or len(topic_name.strip()) < 8:
        errors_found.append("topic_name is missing or too vague")

    if not quote:
        errors_found.append("quote is missing")

    if profile == "cartoon":
        quote_hindi = content.get("quote_hindi", "")
        if not quote_hindi:
            errors_found.append("quote_hindi is missing")
        quote_words = _word_count(quote)
        if quote_words and not (45 <= quote_words <= 90):
            errors_found.append(f"cartoon script should be about 50-80 words, got {quote_words}")
        if not isinstance(video_keywords, list) or len(video_keywords) != 4:
            errors_found.append("cartoon video_search_keywords must contain exactly 4 items")
        allowed_video_keywords = {
            "soap cutting", "slime", "kinetic sand", "sand art", "clay cutting",
            "water drops", "sand pouring", "marble run", "color powder", "paint mixing",
            "pottery", "domino", "bubble wrap", "satisfying",
        }
        keywords_to_validate = video_keywords if isinstance(video_keywords, list) else []
        invalid_video_keywords = [
            kw for kw in keywords_to_validate
            if str(kw).strip().lower() not in allowed_video_keywords
        ]
        if invalid_video_keywords:
            errors_found.append(f"cartoon video keywords must come from the proven list: {invalid_video_keywords[:3]}")
        music_keyword = str(content.get("music_search_keyword", "")).strip().lower()
        if music_keyword not in {"quirky", "playful", "upbeat"}:
            errors_found.append("cartoon music_search_keyword must be quirky, playful, or upbeat")
        retention_beats = content.get("retention_beats", [])
        if not isinstance(retention_beats, list) or len(retention_beats) != 4:
            errors_found.append("cartoon retention_beats must contain exactly 4 beats")
        for required_field in ("joke_engine", "hook_type", "punchline_quality_check"):
            if not content.get(required_field):
                errors_found.append(f"{required_field} is missing")
    else:
        quote_words = _word_count(quote)
        if quote_words and not (80 <= quote_words <= 105):
            errors_found.append(f"NextGenThoughts script must be 80-100 words, got {quote_words}")
        if not content.get("creative_angle"):
            errors_found.append("creative_angle is missing")
        if not content.get("audience_pain"):
            errors_found.append("audience_pain is missing")
        retention_beats = content.get("retention_beats", [])
        if not isinstance(retention_beats, list) or len(retention_beats) < 4:
            errors_found.append("retention_beats must contain at least 4 beats")
        if not isinstance(video_keywords, list) or not (5 <= len(video_keywords) <= 8):
            errors_found.append("NextGenThoughts video_search_keywords must contain 5 to 8 items")
        banned_visual_terms = {
            "psychology", "mindset", "success", "manipulation", "power", "sadness",
            "motivation", "confidence", "discipline", "dark psychology"
        }
        bad_keywords = [
            kw for kw in video_keywords
            if any(term in str(kw).lower() for term in banned_visual_terms)
        ]
        if bad_keywords:
            errors_found.append(f"video keywords must be literal physical visuals, not abstract terms: {bad_keywords[:3]}")

    if fomo_overlay and _word_count(fomo_overlay) > 8:
        errors_found.append("fomo_overlay is too long")

    yt_tags = content.get("yt_tags", [])
    if yt_tags and not isinstance(yt_tags, list):
        errors_found.append("yt_tags must be a list")
    elif profile != "cartoon" and yt_tags:
        normalized_tags = [str(tag).strip().lower() for tag in yt_tags]
        devanagari_tags = [tag for tag in normalized_tags if re.search(r"[\u0900-\u097F]", tag)]
        roman_hindi_terms = (
            "hindi", "kaise", "kya", "kyu", "kyun", "manovigyan",
            "dimag", "dimaag", "soch", "rishta", "log", "insaan",
        )
        roman_hindi_tags = [
            tag for tag in normalized_tags
            if any(term in tag for term in roman_hindi_terms)
        ]
        if len(yt_tags) < 20:
            errors_found.append("NextGenThoughts yt_tags should contain at least 20 tags")
        if len(devanagari_tags) < 3:
            errors_found.append("NextGenThoughts yt_tags must include at least 3 Devanagari Hindi tags")
        if len(roman_hindi_tags) < 5:
            errors_found.append("NextGenThoughts yt_tags must include at least 5 Romanized Hindi/Hinglish tags")

    return errors_found


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

    MASTER_TOPIC_LIST = ""

    # --- SELF HEALING INJECTION ---
    directives_injection = ""
    directives_file = "ai_directives_cartoon.txt" if profile == "cartoon" else "ai_directives.txt"

    if os.path.exists(directives_file):
        with open(directives_file, "r", encoding="utf-8") as f:
            directives_txt = f.read().strip()
            if directives_txt:
                directives_injection = (
                    "CRITICAL DIRECTIVES FROM RECENT PERFORMANCE ANALYTICS:\n"
                    f"{directives_txt}\n"
                    "You MUST obey these rules, as they were derived from real audience data.\n\n"
                )

    if profile == "cartoon":
        prompt = (
            f"{directives_injection}"
            "You are a scriptwriter for 'Cartoon Plus', a YouTube channel that posts funny Hindi shorts. "
            "Your videos combine calming background footage (like soap cutting or ASMR) with a hilarious, conversational Hindi story or joke. "
            "Write a short, engaging, and very funny Hindi story or joke that feels native to Indian family, school, office, or phone-life comedy. "
            "DO NOT hardcode exactly 'Ek bar Pintu ne bola...', be creative and come up with your own funny setups and characters (e.g. Chintu, Mummy, Papa, Teacher, Boss, Padosi, Sharma ji). "
            "Avoid stale WhatsApp-forward jokes, generic moral stories, and predictable one-line riddles.\n\n"

            "CREATOR PRODUCTION WORKFLOW (do this internally before writing):\n"
            "1. PREMISE: Pick one concrete everyday situation with built-in tension: secret exposed, naive child logic, school trouble, family bargaining, phone/tech confusion, office excuse, or neighbor comparison.\n"
            "2. COMEDY ENGINE: Choose ONE joke engine and commit to it: misunderstanding, reverse logic, secret reveal, over-literal child answer, status embarrassment, or unexpected adult hypocrisy.\n"
            "3. RETENTION LADDER: Build four beats: instant conflict, escalation, suspense pause/CTA, punchline twist. Every line must push to the next beat.\n"
            "4. PUNCHLINE TEST: The final line must reframe the whole setup. If the punchline could be guessed from line one, rewrite it.\n"
            "5. REWATCH LOOP: End with a punchline that makes the opening funnier when replayed. Do not explain the joke after the punchline.\n\n"

            "SCRIPT STRUCTURE (Strictly follow this):\n"
            "1. THE HOOK (0-3 seconds): Start mid-conflict with a concrete line, not intro narration. Example style: 'Teacher ne Chintu se poocha...' or 'Papa ka phone dekhte hi Chintu chillaya...' but invent your own.\n"
            "2. THE SETUP: Use quick back-and-forth dialogue. Keep sentences short, spoken, and easy for subtitles.\n"
            "3. THE SUSPENSE CTA: Right before the final punchline, insert ONE natural like/subscribe CTA in the character's voice or narrator voice. Keep it under 12 words. Vary it naturally.\n"
            "4. THE PUNCHLINE: Deliver the twist immediately after the CTA. No extra explanation, no second ending.\n\n"

            "LANGUAGE RULES:\n"
            "   - You MUST generate TWO versions of the script.\n"
            "   - Version 1 ('quote'): Conversational Roman Hindi (Hinglish) for on-screen subtitles. Easy to read for Gen Z.\n"
            "   - Version 2 ('quote_hindi'): Proper Devanagari script (e.g. 'एक बार पिंटू ने बोला...') for the AI voice to read perfectly natively.\n"
            "   - NO markdown: no **, no __, no #. Plain spoken text only.\n"
            "   - Script length: around 50 to 80 words.\n\n"

            "PLATFORM SEO METADATA:\n"
            "   - YOUTUBE SHORTS: A clickbaity, funny Hindi title WITH EMOJIS under 80 characters. IMPORTANT: At the very end of the title, append 2-3 of the most relevant hashtags (e.g. '#shorts #funny #hindi'). Example: 'Teacher ne Pappu ko class se nikala 😂 #shorts #funny #hindi'.\n"
            "   - DESCRIPTION: 2-3 lines in Hindi/Hinglish with emojis. Keep it fun and short, and append 3-5 relevant hashtags at the very end.\n"
            "   - YOUTUBE TAGS (MOST IMPORTANT): Generate exactly 25 to 30 tags for maximum reach. Mix ALL of these categories:\n"
            "       * Core viral tags: shorts, ytshorts, viral shorts, trending shorts, funny shorts, comedy shorts\n"
            "       * Hindi-specific: hindi comedy, hindi funny video, hindi jokes, funny hindi shorts, desi comedy\n"
            "       * Character/story tags based on the joke (e.g. teacher student joke, pappu joke, dost yaar joke)\n"
            "       * Relatable life tags: school life, office life, family comedy, desi life, indian comedy\n"
            "       * Discovery tags: new shorts, popular shorts, shorts feed, you tube shorts, short video\n"
            "       * Channel tag: Cartoon Plus\n"
            "     RULES: Tags must NOT include '#'. Each tag is a plain string. Mix single words and 2-4 word phrases.\n\n"
            "   - FACEBOOK/IG REELS: A short funny caption with emojis and hashtags.\n\n"

            "VIDEO ASSETS:\n"
            "   - Provide EXACTLY 4 background video keywords for satisfying/ASMR clips. MUST BE ENGLISH.\n"
            "   - Pick ONLY from this proven list (these actually return good results on Pexels):\n"
            "     'soap cutting', 'slime', 'kinetic sand', 'sand art', 'clay cutting',\n"
            "     'water drops', 'sand pouring', 'marble run', 'color powder', 'paint mixing',\n"
            "     'pottery', 'domino', 'bubble wrap', 'satisfying'\n"
            "   - Do NOT invent keywords outside this list.\n"
            "   - One background music keyword: use ONLY one of these: 'quirky', 'playful', 'upbeat'.\n\n"

            "OUTPUT FORMAT: Single valid JSON object. NO markdown wrapping.\n"
            "{\n"
            "  \"topic_name\": \"Short description of the joke (for history tracking)\",\n"
            "  \"joke_engine\": \"misunderstanding | reverse logic | secret reveal | over-literal child answer | status embarrassment | adult hypocrisy\",\n"
            "  \"hook_type\": \"the exact hook style used\",\n"
            "  \"retention_beats\": [\"instant conflict\", \"escalation\", \"suspense CTA\", \"punchline twist\"],\n"
            "  \"punchline_quality_check\": \"why the final line is surprising and replayable\",\n"
            "  \"quote\": \"the full spoken script in Roman Hindi (Hinglish)\",\n"
            "  \"quote_hindi\": \"the EXACT SAME script in proper Devanagari Hindi\",\n"
            "  \"fomo_overlay\": \"Wait for it... 🤣\",\n"
            "  \"video_search_keywords\": [\"soap cutting\", \"slime\", \"kinetic sand\", \"satisfying\"],\n"
            "  \"music_search_keyword\": \"quirky\",\n"
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
        prompt = (
            f"{directives_injection}"
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

            "CREATOR PRODUCTION WORKFLOW (do this internally before writing):\n"
            "1. TOPIC SELECTION: Use the master library as the channel canon. Choose an unused book law or named concept first. "
            "Only move outside the library when the used-topic history makes the library too repetitive.\n"
            "2. RESEARCH SYNTHESIS: If a web research brief is provided, use it to sharpen the angle, audience pain, title language, "
            "and real-world scenario. Never copy web wording. Turn research into an original teaching moment.\n"
            "3. ANGLE DESIGN: Pick ONE dominant emotional engine: fear, betrayal, status loss, forbidden knowledge, identity threat, "
            "social proof shock, or self-respect. The entire script must serve that one engine.\n"
            "4. RETENTION LADDER: Build four beats: interrupt pattern, name the hidden rule, show the everyday trap, give the power move. "
            "Each beat must make the next line feel necessary.\n"
            "5. CREATOR FILTER: A real YouTuber would reject generic advice. Make the script concrete, cinematic, slightly dangerous, "
            "and immediately useful.\n\n"

            "SCRIPT STRUCTURE (follow this exact emotional arc):\n"
            "1. THE HOOK (0-3 Seconds) — INVENT YOUR OWN UNIQUE HOOK STYLE for this specific topic. "
            "Do NOT default to generic or repetitive patterns. You must design the opening strategy that will cause the "
            "maximum number of people to stop scrolling for THIS particular concept. "
            "Ask yourself: what is the most psychologically disruptive, emotionally provocative, or counterintuitive angle "
            "of this specific topic? Then open with THAT. "
            "Great hooks exploit one of these deep human drives: "
            "curiosity (make them feel they are about to learn a secret), "
            "fear (make them feel something bad is happening to them right now), "
            "identity threat (attack a belief they hold about themselves), "
            "social proof shock (make them question everyone around them), "
            "forbidden knowledge (make them feel society is hiding this from them), "
            "personal confession (raw vulnerable narrator voice that draws them in), "
            "or a completely novel angle you invent yourself that is even more powerful. "
            "1-2 punchy, scroll-stopping sentences MAX. Every word must earn its place. "
            "Record the hook style you invented in the 'hook_archetype' JSON field.\n"

            "2. THE REVEAL — Immediately after the hook, name the psychological concept or law. "
            "Do NOT copy the same framing every time. Invent the best possible reveal for THIS specific concept. "
            "A great reveal does three things: (a) it NAMES the concept clearly so the viewer has a label to hold onto, "
            "(b) it FRAMES it as rare, forbidden, or misunderstood knowledge — something most people will never know, "
            "(c) it creates an AHA PIVOT that makes the hook make sense: the viewer suddenly understands WHY the opening was so alarming. "
            "You can frame it through a book ('Robert Greene called it...'), a historical figure, a clinical term made human, "
            "a phrase you coin yourself, or any other angle that fits the concept best. "
            "1-3 sentences. Sharp and clean.\n"

            "3. THE TEACHING — This is your masterclass. Explain HOW and WHY this works using a vivid, "
            "relatable real-world story or scenario. Write in short, punchy sentences. "
            "Vary sentence length for dramatic effect. Use 'you' and 'your' to speak directly to ONE person. "
            "BANNED phrases: 'cognitive bias', 'research shows', 'studies have found', 'it is important to note', "
            "'this phenomenon', 'in conclusion', 'psychologists say', 'according to'. "
            "Teach it like you are revealing a dangerous secret to your smartest friend.\n"

            "4. THE POWER MOVE — End with one actionable, empowering takeaway. "
            "How can they use this or protect themselves from it?\n"

            "5. THE LOOP CLOSER (CRITICAL RULE) — The VERY LAST sentence of the script MUST echo or "
            "mirror the exact theme or key phrase from the opening hook, so the video loops seamlessly. "
            "Example: If the hook was 'Stop choosing people who hurt you', the loop closer might be "
            "'Because now you know exactly why you kept choosing them, and you never have to again.' "
            "This is not optional. It creates a seamless infinite loop effect for YouTube Shorts replays, "
            "which dramatically boosts watch time percentage.\n\n"

            "LANGUAGE RULES:\n"
            "   - NO markdown: no **, no __, no #. Plain spoken English only.\n"
            "   - NO special characters or symbols.\n"
            "   - LENGTH CONSTRAINT: Your final spoken script (the 'quote' field) MUST be strictly between 80 to 100 words. "
            "Every word must hit hard.\n\n"

            "PLATFORM SEO METADATA (generate after the script):\n"
            "   - YOUTUBE SHORTS TITLE: Put the main searchable keyword in the first 45 characters, then add emotion/curiosity. Use emojis only if they make the title more clickable. Keep under 80 characters. Append 2-3 relevant hashtags at the very end, such as '#shorts #psychology #hindi'.\n"
            "   - YOUTUBE DESCRIPTION: Write a rich, multi-paragraph description (minimum 150 words). Include the exact topic name in the first two lines. Organically mix English, Romanized Hindi, and Devanagari Hindi search phrases such as 'dark psychology tricks in hindi', 'kaise samjhe', 'manipulation secrets', 'मानव मनोविज्ञान', 'डार्क साइकोलॉजी', and 'रिश्तों की सच्चाई'. End with 5-8 directly relevant hashtags, never a spam wall.\n"
            "   - YOUTUBE TAGS: Generate exactly 25 to 30 plain-string tags with NO '#'. Mix these categories: English high-intent tags, Romanized Hindi/Hinglish tags, Devanagari Hindi tags, topic-specific tags, common misspellings, and channel/brand tags. Include at least 5 Romanized Hindi tags and at least 3 Devanagari Hindi tags. Examples: 'dark psychology in hindi', 'manipulation kaise samjhe', 'human psychology hindi', 'मानव मनोविज्ञान', 'डार्क साइकोलॉजी', 'रिश्ते psychology', 'NextGenThoughts'.\n"
            "   - FACEBOOK REELS: A warm, conversational caption ending with a thought-provoking question. Exactly 7 viral hashtags. Include one Hindi or Hinglish phrase naturally.\n"
            "   - INSTAGRAM REELS: A short, minimalistic, aesthetic caption. Max 2 lines. 2-3 emojis. 6-8 niche hashtags, mixing English and Hindi/Hinglish discovery terms.\n"
            "   CRITICAL: #NextGenThoughts MUST be the first hashtag on every single platform.\n\n"

            "PLATFORM SEO METADATA (generate after the script):\n"
            "   - YOUTUBE SHORTS: A scroll-stopping title WITH EMOJIS (under 80 chars, urgent or forbidden feeling). IMPORTANT: At the very end of the title, append 2-3 of the most relevant hashtags (e.g. '#shorts #psychology'). "
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
            "The 'hook_archetype' field must record which hook style was used (e.g. 'VIVID SCENE').\n"
            "The 'creative_angle' field must explain the one-line angle used for this video.\n"
            "The 'audience_pain' field must name the viewer fear/problem targeted.\n"
            "The 'retention_beats' field must list 4 short beats that shaped the script.\n"
            "The 'fomo_overlay' is a short, clickbaity half-caption that stays on screen (e.g. 'The real reason they ignore you...'). Max 7 words.\n"
            "{\n"
            "  \"topic_name\": \"...\",\n"
            "  \"hook_archetype\": \"...\",\n"
            "  \"creative_angle\": \"...\",\n"
            "  \"audience_pain\": \"...\",\n"
            "  \"retention_beats\": [\"interrupt\", \"hidden rule\", \"trap\", \"power move\"],\n"
            "  \"quote\": \"the full spoken script with loop closer at the end\",\n"
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
            "Pick the most surprising, counterintuitive, or rarely-discussed unused entry, then use the web research brief "
            "to make that topic feel current, specific, and emotionally sharp. "
            "If ALL entries in the library have been used, use the research brief to invent a new niche dark psychology concept with the same depth. "
            "The topic_name MUST follow the format: '[Book Title] — [Law/Concept]' for book-based topics. "
            "Now generate a completely fresh, original script."
        )

    research_brief_payload = None
    research_brief_file = None

    if _env_flag("GEMINI_ENABLE_RESEARCH", True):
        research_models = _profile_model_list(profile, "GEMINI_CARTOON_RESEARCH_MODELS", "GEMINI_RESEARCH_MODELS", DEFAULT_RESEARCH_MODELS)
        research_prompt = _build_research_prompt(profile, used_topics, MASTER_TOPIC_LIST)
        research_brief = _call_gemini_text_with_fallback(
            contents=research_prompt,
            models_to_try=research_models,
            use_search=True,
            purpose="Research brief",
        )
        if research_brief:
            research_brief_file = _research_brief_path(profile)
            research_brief_payload = _save_research_brief(profile, research_brief)
            print("\n" + "=" * 60)
            print("🧠 GEMINI RESEARCH BRIEF")
            print("=" * 60)
            print(json.dumps(research_brief_payload, ensure_ascii=False, indent=2))
            print("=" * 60)
            print(f"Research brief saved to {research_brief_file}")
            prompt += (
                "\n\n--- CURRENT WEB RESEARCH BRIEF (use this as creative direction) ---\n"
                f"{research_brief}\n"
                "----------------------------------------------\n"
                "Use the brief to choose a fresher angle, sharper hook, better story scenario, "
                "and stronger metadata. Do not copy web text. Synthesize an original script.\n"
            )
        else:
            print("⚠️  Research brief unavailable. Continuing with built-in topic library only.")
    else:
        print("Gemini research step disabled via GEMINI_ENABLE_RESEARCH=false.")

    # ── Gemini model priority list: best first, fall back down the chain ────────
    # Strategy (Model-Outer / Key-Inner): prefer better models first and rotate
    # keys for quota/auth errors. For 503/504 backend errors or timeout, skip the
    # model quickly because retrying more keys hits the same overloaded backend.
    MODELS_BY_PRIORITY = _profile_model_list(profile, "GEMINI_CARTOON_WRITER_MODELS", "GEMINI_WRITER_MODELS", DEFAULT_WRITER_MODELS)

    # Track topics rejected THIS SESSION so we can re-inject them into the
    # prompt. This forces Gemini to pick a genuinely different topic instead
    # of returning the same cached response.
    rejected_topics: list[str] = []
    quality_feedback: list[str] = []

    def build_current_prompt() -> str:
        """Rebuild prompt with any runtime-rejected topics appended."""
        if not rejected_topics and not quality_feedback:
            return prompt
        rejection_note = ""
        if rejected_topics:
            rejection_note += (
                "\n\nDO NOT write about these previously generated topics (rejected this session):\n"
                + "\n".join(f"- {t}" for t in rejected_topics)
                + "\n"
            )
        if quality_feedback:
            rejection_note += (
                "\n\nFix these quality issues from previous rejected drafts:\n"
                + "\n".join(f"- {item}" for item in quality_feedback[-3:])
                + "\n"
            )
        return prompt + rejection_note

    response = None
    raw_text = ""
    generation_config = _gemini_search_config() if _env_flag("GEMINI_ENABLE_WRITER_GOOGLE_SEARCH") else None
    if generation_config:
        print("Gemini writer Google Search grounding enabled via GEMINI_ENABLE_WRITER_GOOGLE_SEARCH.")

    for model_name in MODELS_BY_PRIORITY:
        if response:
            break  # Already succeeded — stop

        # Snapshot all currently available keys (shuffled) for this model tier.
        keys_to_try = gemini_rotator.get_all_keys()
        if not keys_to_try:
            print("All Gemini API keys exhausted.")
            break

        print(f"\n📡 Trying model '{model_name}' across {len(keys_to_try)} key(s)...")

        skip_model = False
        for current_key in keys_to_try:
            if not gemini_rotator.has_keys():
                break  # All keys removed mid-loop

            client = create_gemini_client(current_key)
            current_prompt = build_current_prompt()

            max_attempts_this_key = 3  # Duplicate retries on the same key
            attempt = 0

            while attempt < max_attempts_this_key:
                attempt += 1
                try:
                    print(f"  Trying key {current_key[:8]}... (attempt {attempt})")
                    request_kwargs = {
                        "model": model_name,
                        "contents": current_prompt,
                    }
                    if generation_config:
                        request_kwargs["config"] = generation_config

                    resp = client.models.generate_content(**request_kwargs)
                    raw_text = resp.text.strip()
                    print(f"  ✅ Raw response received from '{model_name}'")

                    # ── Parse & validate ──────────────────────────────────────
                    start_idx = raw_text.find('{')
                    end_idx = raw_text.rfind('}')
                    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
                        raise json.JSONDecodeError("No JSON object found.", raw_text, 0)
                    content = json.loads(raw_text[start_idx:end_idx+1].strip())

                    topic_name = content.get('topic_name', content.get('quote', '')[:60])

                    # ── HARD DUPLICATE GUARD ──────────────────────────────────
                    if _is_topic_duplicate(topic_name, used_topics) or topic_name in rejected_topics:
                        print(f"  ⚠️  Duplicate topic detected: '{topic_name}'")
                        print(f"      Adding to session rejection list and sleeping 5s to reset RPM window...")
                        rejected_topics.append(topic_name)
                        current_prompt = build_current_prompt()
                        raw_text = ""
                        time.sleep(5)   # Let the sliding RPM window partially reset
                        continue        # Retry same key with updated prompt
                    # ─────────────────────────────────────────────────────────

                    quality_errors = _content_quality_errors(content, profile)
                    if quality_errors:
                        print("  ⚠️  Draft failed quality checks:")
                        for item in quality_errors:
                            print(f"      - {item}")
                        quality_feedback.append("; ".join(quality_errors))
                        current_prompt = build_current_prompt()
                        raw_text = ""
                        time.sleep(3)
                        continue

                    # Persist only the topic name to history (not the full script).
                    with open(history_file, "a", encoding="utf-8") as f:
                        f.write(f"- {topic_name}\n")

                    print(f"  ✅ Fresh topic selected: '{topic_name}'")
                    if research_brief_payload:
                        content["research_brief"] = research_brief_payload
                    if research_brief_file:
                        content["research_brief_file"] = research_brief_file
                    response = content
                    break  # Done — exit duplicate-retry loop

                except errors.APIError as e:
                    print(f"  Gemini API Error — model '{model_name}', key {current_key[:8]}...: {e}")
                    code = getattr(e, 'code', None)
                    if is_gemini_model_overloaded(e):
                        print(f"  ↳ 503/504 backend timeout or high demand on '{model_name}'. Skipping this model tier instead of trying more keys...")
                        skip_model = True
                        break
                    if code == 429:
                        error_str = str(e).lower()
                        if "quota" in error_str or "exhausted" in error_str:
                            print(f"  ↳ 429 Quota exhausted for this model. Moving to next key...")
                            # Quotas can be per-model, so we don't remove the key globally.
                            # We also don't sleep, because sleeping won't fix a hard quota limit.
                        else:
                            print(f"  ↳ 429 rate limit. Sleeping 3s, then trying next key...")
                            time.sleep(3)
                        break           # Move to next key for this model tier
                    elif getattr(e, 'code', None) == 403:
                        print(f"  ↳ 403 Forbidden (Invalid Key). Removing key globally...")
                        gemini_rotator.remove_key(current_key)
                        break           # Move to next key
                    elif getattr(e, 'code', None) in (404, 400):
                        print(f"  ↳ Model error ({getattr(e, 'code', None)}). Moving to next model tier...")
                        skip_model = True
                        break           # Exit while loop, flag to skip model
                    else:
                        print(f"  ↳ Other API error ({getattr(e, 'code', None)}). Moving to next key...")
                        break

                except json.JSONDecodeError:
                    print("  JSON decode failed. Raw output (first 300 chars):")
                    print(raw_text[:300])
                    raw_text = ""
                    break  # Try next key

                except Exception as e:
                    if is_gemini_timeout(e):
                        print(f"  ↳ Gemini request timed out on '{model_name}'. Skipping this model tier...")
                        skip_model = True
                        break
                    print(f"  Unexpected error: {e}")
                    break  # Try next key

            if response or skip_model:
                break  # Exit key loop — we're done or model is skipping

        if not response:
            print(f"  ⚠️  Model '{model_name}' exhausted across all keys. Falling back to next model tier...")

    if not response:
        print("All Gemini model tiers and API keys exhausted. Aborting.")
        return {}

    return response

if __name__ == "__main__":
    print(generate_content())
