import base64
import hashlib
import os
import traceback
from typing import Optional

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from keystore import keystore

# Create the router instance
router = APIRouter(prefix="/api/key", tags=["api_key"])

# Global variables to store references to the models and workflow
# These will be set by the backend_server_async.py
graph_app_instance = None
checkpointer_instance = None
inner_agent_app_instance = None

# Default session ID for backward compatibility
DEFAULT_SESSION_ID = "default"


# Model for API key submission
class ApiKeyRequest(BaseModel):
    encrypted_key: str
    session_id: Optional[str] = None


# Fixed encryption key - must match the frontend
SECRET_KEY = os.environ["ENCRYPTION_SECRET"]
print(SECRET_KEY)


# Decrypt the API key from the frontend
def decrypt_api_key(encrypted_data: str) -> Optional[str]:
    try:
        print(f"Attempting to decrypt API key, length: {len(encrypted_data)}")
        # Parse the CryptoJS format
        # CryptoJS format is a string like: "U2FsdGVkX1..." which is a base64 encoded string
        # that contains the salt, iv, and ciphertext

        # Decode the base64 string
        ciphertext = base64.b64decode(encrypted_data)

        # CryptoJS format: "Salted__" + 8 byte salt + ciphertext
        if not ciphertext.startswith(b"Salted__"):
            raise ValueError("Invalid CryptoJS format: missing 'Salted__' prefix")

        # Extract the salt (8 bytes after "Salted__")
        salt = ciphertext[8:16]
        actual_ciphertext = ciphertext[16:]

        # Derive key and IV using the same method as CryptoJS
        # CryptoJS derives key and IV using OpenSSL's EVP_BytesToKey
        derived = b""
        key_iv = b""

        # Recreate the key derivation process
        while len(key_iv) < 48:  # We need 32 bytes for key and 16 bytes for IV
            md5 = hashlib.md5()
            md5.update(derived + SECRET_KEY.encode("utf-8") + salt)
            derived = md5.digest()
            key_iv += derived

        key = key_iv[:32]  # First 32 bytes for the key
        iv = key_iv[32:48]  # Next 16 bytes for the IV

        # Create AES cipher in CBC mode using cryptography library
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(actual_ciphertext) + decryptor.finalize()

        # Unpad the data
        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
        decrypted = unpadder.update(padded_data) + unpadder.finalize()

        # Convert to string
        decrypted_key = decrypted.decode("utf-8")
        print("decrypted_key: ", decrypted_key)

        print(f"Decryption successful, key length: {len(decrypted_key)}")
        return decrypted_key

    except Exception as e:
        print(f"Error decrypting API key: {e}")
        traceback.print_exc()

        # If decryption fails, return None instead of using the encrypted key
        print("Decryption failed, returning None")
        return None


async def reinitialize_models(session_id: str):
    """Reinitialize the models and workflow with the new API key.

    This function is called when the API key is set through the API endpoint.
    It recreates the models and workflow using the new API key.

    Args:
        session_id: The session ID associated with the API key
    """
    global graph_app_instance, checkpointer_instance, inner_agent_app_instance

    # Import here to avoid circular imports
    from superego_core_async import create_models, create_workflow

    try:
        print(f"Reinitializing models for session {session_id}...")

        # Get the API key from the keystore
        api_key = keystore.get_key(session_id)
        if not api_key:
            print(f"Error: API key not found in keystore for session {session_id}")
            return False
        print(
            f"API key found in keystore for session {session_id}, length: {len(api_key)}"
        )

        # Create new models with the API key
        superego_model, inner_model = create_models(api_key)

        # If models were created successfully, recreate the workflow
        if superego_model is not None and inner_model is not None:
            # Create new workflow with the new models
            new_graph_app, checkpointer, new_inner_agent_app = await create_workflow(
                superego_model=superego_model, inner_model=inner_model
            )

            # Update the global instances
            graph_app_instance = new_graph_app
            inner_agent_app_instance = new_inner_agent_app
            # Note: We don't update checkpointer_instance as it should remain the same

            print(
                f"Models and workflow reinitialized successfully for session {session_id}"
            )
            return True
        else:
            print(f"Failed to create models with the API key for session {session_id}")
            return False
    except Exception as e:
        print(f"Error reinitializing models: {e}")
        traceback.print_exc()
        return False


@router.post("/set")
async def set_api_key(request: ApiKeyRequest):
    """Sets the API key for the backend server."""
    try:
        # Validate request
        print(
            f"Encrypted key received, length: {len(request.encrypted_key) if request.encrypted_key else 0}"
        )

        if not request.encrypted_key:
            # Instead of raising an exception, return a message prompting for an API key
            return {
                "status": "needs_api_key",  # Match the status used elsewhere
                "message": "Please enter your Anthropic API key in the top left corner for your session",
                "is_error": False,  # Indicate this is not a critical error but a setup step
                "first_time_setup": True,  # Indicate this is likely a first-time setup
            }

        # Decrypt the API key
        decrypted_key = decrypt_api_key(request.encrypted_key)
        print(f"Decryption result: {'Success' if decrypted_key else 'Failed'}")

        if not decrypted_key:
            # Return a message indicating decryption failed
            return {
                "status": "error",
                "message": "Failed to decrypt API key. Please try again with a valid key.",
            }

        # Use the provided session ID or generate a new one
        session_id = request.session_id or DEFAULT_SESSION_ID

        # Check if the API key has changed
        current_key = keystore.get_key(session_id)
        key_changed = current_key != decrypted_key

        # Store the API key in the keystore
        keystore.set_key(session_id, decrypted_key)
        print(
            f"API key stored in keystore for session {session_id}, length: {len(decrypted_key)}"
        )

        # Verify the key is accessible
        test_key = keystore.get_key(session_id)
        if test_key != decrypted_key:
            print(
                f"Warning: API key not stored correctly in keystore for session {session_id}"
            )
            return {
                "status": "error",
                "message": "Failed to store API key. Please try again.",
            }

        print(f"API key has been set successfully for session {session_id}")

        # If the key has changed, reinitialize the models
        if key_changed:
            success = await reinitialize_models(session_id)
            if success:
                return {
                    "status": "success",
                    "message": "API key has been set and models reinitialized successfully",
                    "session_id": session_id,
                }
            else:
                return {
                    "status": "partial_success",
                    "message": "API key has been set but models could not be reinitialized",
                    "session_id": session_id,
                }

        return {
            "status": "success",
            "message": "API key has been set successfully",
            "session_id": session_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error setting API key: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/check")
async def check_api_key(session_id: Optional[str] = None):
    """Check if an API key is set for the specified session."""
    # Use the provided session ID or the default
    session_id = session_id or DEFAULT_SESSION_ID

    # Check if the session has an API key
    has_key = keystore.has_key(session_id)

    if has_key:
        return {
            "status": "success",
            "message": f"API key is set for session {session_id}",
            "has_key": True,
            "session_id": session_id,
        }
    else:
        return {
            "status": "needs_api_key",  # Match the status used in runs.py
            "message": f"No API key set for session {session_id}. Please set an API key.",
            "has_key": False,
            "session_id": session_id,
            "is_error": False,  # Indicate this is not a critical error but a setup step
            "first_time_setup": True,  # Indicate this is likely a first-time setup
        }


@router.get("/sessions")
async def list_sessions():
    """List all sessions with API keys."""
    sessions = keystore.get_all_sessions()
    return {
        "status": "success",
        "sessions": sessions,
        "count": len(sessions),
    }
