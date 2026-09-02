import os
import sys
import argparse
from google.genai import errors
from dotenv import load_dotenv
from src.api_manager import create_gemini_client, is_gemini_model_overloaded, is_gemini_timeout

load_dotenv()

parser = argparse.ArgumentParser(description="Smoke-test Gemini API keys.")
parser.add_argument("--search", action="store_true", help="Test Google Search-grounded research models.")
args = parser.parse_args()

api_keys = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
if not api_keys:
    raise SystemExit("Set GEMINI_API_KEYS in .env or your shell before running this test.")

writer_models = [
    'gemini-3.7-flash',
    'gemini-3.6-flash',
    'gemini-3.5-flash',
    'gemini-3-flash-preview',
    'gemini-3.5-flash-lite',
    'gemini-3.1-flash-lite',
    'gemini-2.5-flash-lite',
    'gemini-2.5-flash',
]

research_models = [
    'gemini-2.5-flash-lite',
    'gemini-3.1-flash-lite',
    'gemini-3.5-flash-lite',
    'gemini-2.5-flash',
    'gemini-3.5-flash',
]

models = research_models if args.search else writer_models
prompt = "Search the web and reply with one current YouTube Shorts trend in five words." if args.search else "Reply with the word 'Hello'"
config = {"tools": [{"google_search": {}}]} if args.search else None

for api_key in api_keys:
    client = create_gemini_client(api_key)

    print(f"Testing API key: {api_key[:8]}...{api_key[-4:]}")
    print("-" * 50)

    for model in models:
        print(f"Testing model: {model}")
        try:
            request_kwargs = {
                "model": model,
                "contents": prompt,
            }
            if config:
                request_kwargs["config"] = config
            response = client.models.generate_content(**request_kwargs)
            print(f"  ✅ Success! Response: {response.text.strip()}")
        except errors.APIError as e:
            if is_gemini_model_overloaded(e):
                print(f"  ❌ Model backend timeout/high demand: [{getattr(e, 'code', 'Unknown')}] {e}")
                continue
            print(f"  ❌ API Error: [{getattr(e, 'code', 'Unknown')}] {e}")
        except Exception as e:
            if is_gemini_timeout(e):
                print(f"  ❌ Request timed out: {e}")
                continue
            print(f"  ❌ Error: {e}")
        print("-" * 50)
