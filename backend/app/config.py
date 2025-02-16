import os
from pathlib import Path

from dotenv import load_dotenv

env = os.getenv('ENV', 'development')
env_file = Path(__file__).resolve().parent.parent.parent / f'.env.{env}'
print(env_file)
load_dotenv(env_file)
