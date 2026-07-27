"""
src/encryption.py

Day 27: Encryption at rest for stored face embeddings. Directly addresses
the industry-readiness gap flagged in review: embeddings were previously
written to SQLite as raw, unencrypted bytes -- a stolen database file
would directly expose everyone's biometric data in plain, usable form.

Uses Fernet (from the `cryptography` library), a symmetric encryption
scheme that is authenticated (it detects tampering, not just encrypts)
and deliberately simple to use correctly -- a good fit for a single-key,
single-application use case like this, as opposed to asymmetric
encryption (which solves a different problem: multiple parties with
different keys, not needed here).

IMPORTANT: the encryption key itself must NEVER be committed to Git or
stored in the same place as the database file. See key management notes
below.

Usage:
    from src.encryption import encrypt_bytes, decrypt_bytes
    encrypted = encrypt_bytes(embedding.tobytes())
    original_bytes = decrypt_bytes(encrypted)
"""
import os
from cryptography.fernet import Fernet

# Key management: the key is read from an environment variable, NEVER
# hardcoded in source and NEVER committed to version control. In a real
# deployment this would come from a proper secrets manager (AWS Secrets
# Manager, Azure Key Vault, HashiCorp Vault) -- an environment variable is
# the minimum acceptable bar for this project's local/prototype scope,
# one clear step up from "not encrypted at all."
_KEY_ENV_VAR = "FACE_DB_ENCRYPTION_KEY"


def generate_new_key():
    """
    Run this ONCE to generate a new key, then store the output as the
    FACE_DB_ENCRYPTION_KEY environment variable (or in your local .env
    file, which must be listed in .gitignore -- see Day 6's .gitignore,
    already covers .env). Losing this key means every stored embedding
    becomes permanently unreadable -- back it up somewhere safe and
    separate from the database file itself.
    """
    return Fernet.generate_key().decode()


def _get_cipher():
    key = os.environ.get(_KEY_ENV_VAR)
    if not key:
        raise RuntimeError(
            f"{_KEY_ENV_VAR} environment variable not set. "
            f"Run generate_new_key() once, store the result as this "
            f"environment variable, and never commit it to Git."
        )
    return Fernet(key.encode())


def encrypt_bytes(raw_bytes):
    """Encrypts raw bytes (e.g. an embedding's .tobytes() output) before storage."""
    cipher = _get_cipher()
    return cipher.encrypt(raw_bytes)


def decrypt_bytes(encrypted_bytes):
    """
    Decrypts bytes read back from storage. Raises InvalidToken if the key
    is wrong OR if the data was tampered with -- Fernet is authenticated
    encryption, so corruption/tampering is detected, not silently accepted.
    """
    cipher = _get_cipher()
    return cipher.decrypt(encrypted_bytes)


if __name__ == "__main__":
    print("Generating a new encryption key for local development use:")
    print(generate_new_key())
    print("\nStore this as the FACE_DB_ENCRYPTION_KEY environment variable.")
    print("Do NOT commit this key to Git. Do NOT store it in the same")
    print("location as data/face_verification.db.")
