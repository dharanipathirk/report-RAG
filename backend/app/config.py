"""
Configuration module for loading environment variables from a .env file.

The .env file is selected based on the current ENV environment variable.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

env = os.getenv('ENV', 'development')
env_file = Path(__file__).resolve().parent.parent.parent / f'.env.{env}'
load_dotenv(env_file)
