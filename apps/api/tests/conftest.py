"""Test-only configuration applied before application modules are imported."""
import os

# Tests never connect to a developer's PostgreSQL or use their local data.
os.environ["DATABASE_URL"] = "sqlite:///./test_jarvis.db"
os.environ["GEMINI_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
