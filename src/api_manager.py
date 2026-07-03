import os
import random
from dotenv import load_dotenv

load_dotenv()

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

class KeyRotator:
    def __init__(self, keys: list):
        self.keys = keys.copy()
        
    def get_random_key(self):
        """Returns a random key from the available keys."""
        if not self.keys:
            raise ValueError("No API keys available.")
        return random.choice(self.keys)
        
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

gemini_rotator = KeyRotator(gemini_keys)
pexels_rotator = KeyRotator(pexels_keys)
pixabay_rotator = KeyRotator(pixabay_keys)
