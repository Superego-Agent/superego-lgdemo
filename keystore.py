"""
Keystore module for managing API keys by session ID.

This module provides a simple in-memory keystore for storing and retrieving API keys
associated with session IDs. It can be extended to use a persistent storage solution
if needed.
"""

import threading
from typing import Dict, Optional


class KeyStore:
    """
    A thread-safe in-memory store for API keys indexed by session ID.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern to ensure only one keystore instance exists."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(KeyStore, cls).__new__(cls)
                cls._instance._keys = {}  # Initialize the keys dictionary
        return cls._instance

    def __init__(self):
        """Initialize the keystore if it hasn't been initialized yet."""
        if not hasattr(self, "_keys"):
            self._keys: Dict[str, str] = {}

    def set_key(self, session_id: str, api_key: str) -> None:
        """
        Store an API key for a session ID.

        Args:
            session_id: The session ID to associate with the API key
            api_key: The API key to store
        """
        with self._lock:
            self._keys[session_id] = api_key

    def get_key(self, session_id: str) -> Optional[str]:
        """
        Retrieve an API key for a session ID.

        Args:
            session_id: The session ID to retrieve the API key for

        Returns:
            The API key associated with the session ID, or None if not found
        """
        with self._lock:
            return self._keys.get(session_id)

    def delete_key(self, session_id: str) -> bool:
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

    def has_key(self, session_id: str) -> bool:
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


# Create a singleton instance
keystore = KeyStore()
