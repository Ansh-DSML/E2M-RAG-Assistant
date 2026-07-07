"""
Cohere Key Rotation Manager.

Manages a list of Cohere API keys and rotates them automatically if a 429 Rate Limit error occurs.
"""

from __future__ import annotations

import logging
import time
from threading import Lock

import cohere
from cohere.errors import TooManyRequestsError

from app.config import settings

logger = logging.getLogger(__name__)

class CohereKeyManager:
    def __init__(self, api_keys: list[str]):
        if not api_keys:
            raise ValueError("At least one Cohere API key must be provided.")
        
        self.api_keys = api_keys
        # Initialize clients for each key
        self.clients = [cohere.Client(api_key=key) for key in api_keys]
        
        # Track when each key will be free again (timestamp)
        self.key_penalties = [0.0] * len(api_keys)
        
        self.current_idx = 0
        self.lock = Lock()

    def get_client(self) -> tuple[int, cohere.Client]:
        """Get the next available client that is not rate-limited."""
        with self.lock:
            now = time.time()
            
            # Check if current key is free
            if now >= self.key_penalties[self.current_idx]:
                return self.current_idx, self.clients[self.current_idx]
            
            # Current key is penalized, look for the next available one
            for _ in range(len(self.clients)):
                self.current_idx = (self.current_idx + 1) % len(self.clients)
                if now >= self.key_penalties[self.current_idx]:
                    logger.info("Rotated to Cohere key index %d", self.current_idx)
                    return self.current_idx, self.clients[self.current_idx]
            
            # If ALL keys are penalized, return the one that frees up soonest
            # (or just return current and let the caller sleep/fail)
            min_penalty_idx = min(range(len(self.key_penalties)), key=self.key_penalties.__getitem__)
            self.current_idx = min_penalty_idx
            return self.current_idx, self.clients[self.current_idx]

    def penalize_key(self, idx: int, wait_seconds: float = 60.0):
        """Mark a key as rate-limited for a duration."""
        with self.lock:
            self.key_penalties[idx] = time.time() + wait_seconds
            logger.warning("Cohere key index %d penalized for %s seconds due to 429 error", idx, wait_seconds)

# Singleton manager
_manager = None

def get_manager() -> CohereKeyManager:
    global _manager
    if _manager is None:
        _manager = CohereKeyManager(settings.cohere_api_keys_list)
    return _manager

def execute_with_rotation(func, *args, **kwargs):
    """
    Execute a function that takes a cohere.Client as its first argument.
    Automatically rotates keys and retries on 429 TooManyRequestsError.
    """
    manager = get_manager()
    max_retries = len(manager.clients) * 2  # Try each key up to twice
    
    for attempt in range(max_retries):
        idx, client = manager.get_client()
        try:
            return func(client, *args, **kwargs)
        except TooManyRequestsError:
            logger.warning("429 TooManyRequestsError on attempt %d with key index %d", attempt + 1, idx)
            manager.penalize_key(idx, wait_seconds=60.0)
            if attempt == max_retries - 1:
                raise
            # Small sleep before immediate retry on next key
            time.sleep(1)
        except Exception as e:
            # Re-raise non-429 errors immediately
            raise e
