"""
Keystore module for managing API keys by session ID.

This module provides a simple in-memory keystore for storing and retrieving API keys
associated with session IDs. It can be extended to use a persistent storage solution
if needed.
"""

import threading
# Update type hint for nested dictionary
from typing import Dict, Optional


class KeyStore:
    """
    A thread-safe in-memory store for API keys indexed by session ID and provider.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern to ensure only one keystore instance exists."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(KeyStore, cls).__new__(cls)
                # Initialize the keys dictionary with the new structure type hint
                cls._instance._keys: Dict[str, Dict[str, str]] = {}
        return cls._instance

    # __init__ is likely redundant with the singleton's __new__ initialization,
    # but we'll keep the type hint update here for clarity if it remains.
    def __init__(self):
        """Initialize the keystore if it hasn't been initialized yet."""
        if not hasattr(self, "_keys"):
            self._keys: Dict[str, Dict[str, str]] = {}

    # Update type hints for method signature (logic changes will follow)
    def set_key(self, session_id: str, provider: str, api_key: str) -> None:
        """
        Store an API key for a specific provider under a session ID.

        Args:
            session_id: The session ID to associate with the API key
            provider: The provider name (e.g., 'openai', 'anthropic')
            api_key: The API key to store
        """
        with self._lock:
            # Get the dictionary for the session, creating it if it doesn't exist
            session_keys = self._keys.setdefault(session_id, {})
            # Set the key for the specific provider
            session_keys[provider] = api_key

    # Update type hints for method signature
    def get_key(self, session_id: str, provider: str) -> Optional[str]:
        """
        Retrieve an API key for a session ID.

        Args:
            session_id: The session ID to retrieve the API key for
            provider: The provider name to retrieve the key for

        Returns:
            The API key associated with the session ID and provider, or None if not found
        """
        with self._lock:
            # Get the dictionary for the session
            session_keys = self._keys.get(session_id)
            # If the session exists, get the key for the specific provider
            if session_keys:
                return session_keys.get(provider)
            # Return None if session or provider key not found
            return None

    # Rename and update type hint
    def delete_session(self, session_id: str) -> bool:
        """
        Delete an API key for a session ID.

        Args:
            session_id: The session ID to delete the API key for

        Returns:
            True if the key was deleted, False if the session ID was not found
        """
        with self._lock:
            if session_id in self._keys:
                del self._keys[session_id]
                return True
            return False

    # Rename and update type hint
    def has_session(self, session_id: str) -> bool:
        """
        Check if a session ID has an associated API key.

        Args:
            session_id: The session ID to check

        Returns:
            True if the session ID has an associated API key, False otherwise
        """
        with self._lock:
            return session_id in self._keys

    def clear(self) -> None:
        """Clear all keys from the keystore."""
        with self._lock:
            self._keys.clear()

    def get_all_sessions(self) -> list:
        """
        Get a list of all session IDs in the keystore.

        Returns:
            A list of all session IDs
        """
        with self._lock:
            return list(self._keys.keys())

    # Add new method signature
    def get_session_keys(self, session_id: str) -> Optional[Dict[str, str]]:
        """
        Get a dictionary of all provider keys for a session ID.

        Args:
            session_id: The session ID to retrieve keys for

        Returns:
            A dictionary mapping provider names to API keys, or None if session not found.
        """
        with self._lock:
            session_keys = self._keys.get(session_id)
            # Return a copy to prevent external modification of the internal dict
            if session_keys:
                return session_keys.copy()
            return None


# Create a singleton instance
keystore = KeyStore()
