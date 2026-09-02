import os
import random
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

DEFAULT_GEMINI_TIMEOUT_SECONDS = 45
DEFAULT_GEMINI_HTTP_RETRY_ATTEMPTS = 1

def get_keys(env_var_name: str) -> list:
    """
    Reads a comma-separated list of API keys from the environment variable.
    Returns a list of keys, stripped of whitespace.
    """
    raw_val = os.getenv(env_var_name, "")
    if not raw_val:
        return []
    # Handle both comma separated and potentially just a single key
    keys = [k.strip() for k in raw_val.split(",") if k.strip()]
    return keys

def get_positive_int_env(env_var_name: str, default: int) -> int:
    raw_val = os.getenv(env_var_name, "").strip()
    if not raw_val:
        return default
    try:
        value = int(raw_val)
    except ValueError:
        print(f"Invalid {env_var_name}={raw_val!r}. Using default {default}.")
        return default
    if value < 1:
        print(f"{env_var_name} must be at least 1. Using default {default}.")
        return default
    return value

def create_gemini_client(api_key: str):
    timeout_ms = get_positive_int_env(
        "GEMINI_REQUEST_TIMEOUT_SECONDS",
        DEFAULT_GEMINI_TIMEOUT_SECONDS,
    ) * 1000
    retry_attempts = get_positive_int_env(
        "GEMINI_HTTP_RETRY_ATTEMPTS",
        DEFAULT_GEMINI_HTTP_RETRY_ATTEMPTS,
    )
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=timeout_ms,
            retryOptions=types.HttpRetryOptions(
                attempts=retry_attempts,
                initialDelay=1.0,
                maxDelay=3.0,
                expBase=2.0,
                jitter=0.2,
            ),
        ),
    )

def is_gemini_model_overloaded(error) -> bool:
    code = getattr(error, "code", None)
    error_str = str(error).lower()
    return code in (503, 504) or any(
        marker in error_str
        for marker in (
            "503 unavailable",
            "504 deadline_exceeded",
            "deadline_exceeded",
            "deadline expired",
            "high demand",
            "overloaded",
            "service unavailable",
            "try again later",
        )
    )

def is_gemini_timeout(error) -> bool:
    error_name = error.__class__.__name__.lower()
    error_str = str(error).lower()
    return "timeout" in error_name or "timed out" in error_str or "timeout" in error_str

class KeyRotator:
    def __init__(self, keys: list):
        self.keys = keys.copy()
        
    def get_random_key(self):
        """Returns a random key from the available keys."""
        if not self.keys:
            raise ValueError("No API keys available.")
        return random.choice(self.keys)

    def get_all_keys(self):
        """Returns a shuffled copy of all remaining keys."""
        keys_copy = self.keys.copy()
        random.shuffle(keys_copy)
        return keys_copy
        
    def remove_key(self, key):
        """Removes a key that has hit a rate limit or is invalid."""
        if key in self.keys:
            self.keys.remove(key)
            
    def has_keys(self):
        return len(self.keys) > 0

# Initialize rotators
gemini_keys = get_keys("GEMINI_API_KEYS")
pexels_keys = get_keys("PEXELS_API_KEYS")
pixabay_keys = get_keys("PIXABAY_API_KEYS")
elevenlabs_keys = get_keys("ELEVENLABS_API_KEYS")

gemini_rotator = KeyRotator(gemini_keys)
pexels_rotator = KeyRotator(pexels_keys)
pixabay_rotator = KeyRotator(pixabay_keys)
elevenlabs_rotator = KeyRotator(elevenlabs_keys)
