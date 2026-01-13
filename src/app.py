"""
Vercel entry point for Family Scheduler API.

Re-exports the FastAPI app from src/api/main.py for Vercel deployment.
"""

from src.api.main import app

__all__ = ["app"]
