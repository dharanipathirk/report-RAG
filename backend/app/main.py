"""
Main module for starting the FastAPI application.

This module sets up the FastAPI app, mounts static files,
configures CORS middleware, and includes the API endpoints.
"""

import os

import app.config  # Import configuration settings.
from app.api import endpoints
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

app = FastAPI()  # noqa: F811

# Mount static files from the frontend directory.
app.mount('/static', StaticFiles(directory='../frontend/static'), name='static')

# Determine the current environment.
env = os.getenv('ENV', 'development')

# Configure CORS middleware.
origins = os.environ.get('CORS_ORIGINS', '').split(',')
if not origins or origins == ['']:
    origins = ['https://dharanipathi.com'] if env == 'production' else ['*']

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Include API routes.
app.include_router(endpoints.frontend_router)
app.include_router(endpoints.api_router, prefix='/api')
