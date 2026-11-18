"""
Configuration settings for the Free Research Agent.
All key parameters are centralized here so they can be easily modified.
Supports both local Ollama models and cloud-based Google Gemini models.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load secret environment variables from .env file
load_dotenv()

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# --- LLM Provider Settings ---
# Choose your AI provider: "gemini" (Google AI Studio) or "local" (Ollama)
LLM_PROVIDER = "gemini"

# --- Gemini Settings (Cloud - Zero Local RAM Usage) ---
# Model to use from Google AI Studio
GEMINI_MODEL = "gemini-3.5-flash-lite"

# Read API key safely from environment (never hard-coded)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")

# --- Local Ollama Settings (Runs on local machine) ---
MODEL_NAME = "qwen3:1.7b"
OLLAMA_HOST = "http://127.0.0.1:11434"

# Maximum new tokens to generate per response
MAX_TOKENS = 512

# --- Search & Fetching Limits ---
# Number of search queries to generate per topic
QUERIES_PER_TOPIC = 2

# Maximum search results to retrieve per query from DuckDuckGo
RESULTS_PER_QUERY = 3

# Maximum web pages to open and process in total per topic
PAGE_LIMIT = 4

# Maximum characters of text to send to LLM from any single web page
CHAR_LIMIT_PER_PAGE = 4000

# Pause (in seconds) between web requests to be respectful and avoid rate limits
REQUEST_DELAY_SECONDS = 1.5

# HTTP request timeout (in seconds) to avoid hanging on slow websites
REQUEST_TIMEOUT_SECONDS = 10

# Clear User-Agent identifying our local research script
USER_AGENT = "LocalResearchAgent/1.0 (Educational research bot; polite crawler)"

# --- Output Settings ---
# Directory where research reports will be saved
OUTPUT_DIR = BASE_DIR / "output"

# Export formats:
# EXPORT_PDF generates a clean, styled PDF report (Active by default)
EXPORT_PDF = True

# EXPORT_DOCX generates a Microsoft Word document (Off by default)
EXPORT_DOCX = False
