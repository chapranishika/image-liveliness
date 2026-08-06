import os

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
                    val = v.strip().strip("'").strip('"')
                    os.environ[k.strip()] = val
