"""Next Live — Production FastAPI entry point for Cloud Run.

Based on patterns from google/adk-samples (bidi-demo, realtime-conversational-agent).
Uses get_fast_api_app with persistent session storage.
"""

import os

import uvicorn
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app

app: FastAPI = get_fast_api_app(
    agents_dir=os.path.dirname(os.path.abspath(__file__)),
    session_service_uri=os.environ.get(
        "SESSION_DB_URI", "sqlite+aiosqlite:///./sessions.db"
    ),
    allow_origins=["*"],
    web=True,
)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
    )
