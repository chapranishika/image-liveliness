import os
import secrets
from cryptography.fernet import Fernet

def load_env_file():
    """
    Simple custom env loader that parses a local .env file.
    Does not require python-dotenv.
    """
    env_file = ".env"
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    # Strip quotes if present
                    val = v.strip().strip("'").strip('"')
                    os.environ[k.strip()] = val

def init_keys_in_env():
    """
    Ensures FACE_DB_ENCRYPTION_KEY and FACE_API_KEY are configured in the environment.
    If missing, automatically generates secure ones and saves them to .env.
    """
    load_env_file()
    
    # 1. Database Encryption Key
    if not os.environ.get("FACE_DB_ENCRYPTION_KEY"):
        new_key = Fernet.generate_key().decode()
        os.environ["FACE_DB_ENCRYPTION_KEY"] = new_key
        # Append to .env
        with open(".env", "a") as f:
            f.write(f"\n# Secure auto-generated database encryption key\nFACE_DB_ENCRYPTION_KEY={new_key}\n")
        print(f"[Keys] Generated a new secure FACE_DB_ENCRYPTION_KEY and saved to .env")
        
    # 2. Developer API Key
    if not os.environ.get("FACE_API_KEY"):
        new_api_key = f"dev_api_key_{secrets.token_hex(16)}"
        os.environ["FACE_API_KEY"] = new_api_key
        # Append to .env
        with open(".env", "a") as f:
            f.write(f"\n# Secure auto-generated API authentication key\nFACE_API_KEY={new_api_key}\n")
        print(f"[Keys] Generated a new secure FACE_API_KEY and saved to .env")
