import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.api import endpoints

# Load environment variables
env = os.getenv("ENV", "development")
env_file = f".env.{env}"
load_dotenv(env_file)

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="../frontend/static"), name="static")

# Setup CORS middleware
origins = os.environ.get("CORS_ORIGINS", "").split(",")
if not origins or origins == ['']:
    origins = ["https://dharanipathi.com"] if env == "production" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(endpoints.frontend_router)
app.include_router(endpoints.api_router, prefix="/api")
