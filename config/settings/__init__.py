import os
import environ
from pathlib import Path

# Load .env file from this settings folder before choosing the environment settings module
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    environ.Env.read_env(str(env_path))

ENVIRONMENT = os.getenv("DJANGO_ENV", "development")  # Default to development

if ENVIRONMENT == "production":
    from .production import *
else:
    from .development import *
