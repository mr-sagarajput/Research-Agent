# Free Research Agent

A lightweight, beginner-friendly, and 100% free autonomous research assistant written in Python. 

The **Free Research Agent** takes any research topic, generates targeted search queries, searches the web via DuckDuckGo, politely crawls relevant articles with full `robots.txt` compliance, extracts per-page bullet points, and synthesizes a structured topic summary report.

Designed to run smoothly even on entry-level hardware (such as laptops with **4 GB RAM**), the agent supports **dual LLM providers**: cloud-assisted AI via **Google Gemini 3.5 Flash-Lite** (zero local RAM usage) or fully offline, private AI via **Ollama** (`qwen3:1.7b`).

---

## Table of Contents

- [Key Features](#key-features)
- [How It Works](#how-it-works)
- [Project Architecture](#project-architecture)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
  - [1. Clone / Navigate to the Directory](#1-clone--navigate-to-the-directory)
  - [2. Create a Virtual Environment](#2-create-a-virtual-environment-optional-but-recommended)
  - [3. Install Dependencies](#3-install-dependencies)
  - [4. Choose Your AI Provider](#4-choose-your-ai-provider)
- [How to Run](#how-to-run)
  - [Self-Test Mode (1-Page Fast Verification)](#self-test-mode-1-page-fast-verification)
  - [Interactive Mode](#interactive-mode)
  - [Direct Command-Line Topic](#direct-command-line-topic)
- [Configuration Guide (`config.py`)](#configuration-guide-configpy)
- [Troubleshooting](#troubleshooting)
- [Educational Notes (`LEARNING.md`)](#educational-notes-learningmd)
- [License](#license)

---

## Key Features

- **Dual LLM Flexibility (Cloud & Local):**
  - **Google Gemini 3.5 Flash-Lite:** Fast, high-quality cloud intelligence via Google AI Studio's free tier. Consumes **0 MB of local RAM** for inference.
  - **Ollama (`qwen3:1.7b`):** 100% private, offline inference running locally on your CPU/GPU using 4-bit quantization.
- **Multilingual Web Reading (English + Hindi):**
  - Seamlessly fetches and parses articles in English and Hindi (Devanagari script) with full UTF-8 support and URL percent-encoding (`कृत्रिम_बुद्धि` -> `%E0%A4%95...`).
- **Free Web Search (No API Keys Required):**
  - Uses `ddgs` (with automatic fallback to `duckduckgo-search`) to find real-time, live articles without paid search APIs.
- **Strict 4 GB RAM Protection:**
  - Operates on a **one-page-at-a-time streaming pipeline**. Web pages are downloaded, parsed, summarized into notes, and discarded from memory before the next page is fetched.
- **Ethical & Polite Crawling:**
  - Automated `robots.txt` rule checking with `urllib.robotparser`.
  - Transparent, respectful `User-Agent` headers.
  - Configurable inter-request polite delays and timeouts to prevent server strain.
  - Automated HTML element cleaning (`<script>`, `<style>`, `<nav>`, and ads are stripped before processing).
- **Graceful Error Recovery:**
  - Exponential backoff for network rate limits (HTTP 429).
  - Skips broken URLs, forbidden pages (HTTP 403), or blocked domains without crashing the session.

---

## How It Works

```
                        [User Research Topic]
                                  │
                                  ▼
                    [Step 1: Query Generation]
                LLM generates 2 targeted search queries
                                  │
                                  ▼
                     [Step 2: Web Search]
               DuckDuckGo searches candidate articles
                                  │
                                  ▼
               [Step 3: Polite Fetching & Note Extraction]
           For each page (up to PAGE_LIMIT, one at a time):
              ├── Check robots.txt permission
              ├── Download & clean HTML body
              ├── Truncate to memory-safe char limit
              └── LLM extracts 3-5 factual bullet notes
                                  │
                                  ▼
                    [Step 4: Report Synthesis]
            LLM synthesizes an informative ~200-word summary
                using ONLY the extracted factual notes
```

---

## Project Architecture

```text
Research Agent/
├── .env                  # Private API keys (ignored by git)
├── .gitignore            # Git ignore rules for virtualenvs, caches, and secrets
├── config.py             # Central configuration file for all settings
├── LEARNING.md           # Companion educational handbook explaining 30 Python concepts
├── main.py               # Main CLI orchestrator and pipeline execution entry point
├── requirements.txt      # Project dependencies
├── README.md             # Project documentation (this file)
└── modules/
    ├── __init__.py       # Package marker
    ├── fetch.py          # Polite web page fetcher, robots.txt validator, and HTML cleaner
    ├── llm.py            # Provider abstraction layer (Gemini Cloud + Ollama Local)
    └── search.py         # DuckDuckGo search integration and AI query formulation
```

---

## Prerequisites

- **Python 3.10+** (Tested on Python 3.10, 3.11, and 3.12).
- An active Internet connection (for DuckDuckGo web search and Gemini API calls).
- **One of the following AI backends:**
  - **Option A (Cloud - Recommended):** A free Google AI Studio API key.
  - **Option B (Local):** [Ollama](https://ollama.com/) installed and running on your computer.

---

## Installation & Setup

### 1. Clone / Navigate to the Directory

Open your terminal (PowerShell, Command Prompt, or Bash) and navigate to the project directory:

```bash
cd "D:\Projects\Research Agent"
```

### 2. Create a Virtual Environment (Optional but Recommended)

Creating an isolated virtual environment prevents library version conflicts:

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

Install the required Python packages using `pip`:

```bash
pip install -r requirements.txt
```

### 4. Choose Your AI Provider

Open `config.py` in any text editor. Choose your provider by setting `LLM_PROVIDER`:

#### Choice A: Cloud AI with Google Gemini (Recommended for 4 GB RAM)
1. Get a free API key from [Google AI Studio](https://aistudio.google.com/).
2. Create a `.env` file in the project root directory (or edit the existing one):
   ```env
   GEMINI_API_KEY=your_actual_api_key_here
   ```
   *(Note: `GOOGLE_API_KEY` is also supported as an alternate variable name).*
3. In `config.py`, ensure:
   ```python
   LLM_PROVIDER = "gemini"
   GEMINI_MODEL = "gemini-3.5-flash-lite"
   ```

#### Choice B: 100% Offline Local AI with Ollama
1. Download and install Ollama from [ollama.com](https://ollama.com/).
2. Open your terminal and pull the compact, fast 1.7B parameter model:
   ```bash
   ollama pull qwen3:1.7b
   ```
3. Start the Ollama server (if not running as a background service):
   ```bash
   ollama serve
   ```
4. In `config.py`, set:
   ```python
   LLM_PROVIDER = "local"
   MODEL_NAME = "qwen3:1.7b"
   ```

---

## How to Run

### Self-Test Mode (1-Page Fast Verification)

Before running a full multi-page research session, verify your setup using the built-in self-test mode. This mode runs a single search on `"Free local LLMs vs cloud APIs"` and caps scraping at **1 page**:

```bash
python main.py --test
```

### Interactive Mode

Run the script without arguments to be prompted for any research topic:

```bash
python main.py
```

*Example prompt:*
```text
Enter a research topic: Latest breakthroughs in solar cell efficiency
```

### Direct Command-Line Topic

Pass your research topic directly as a command-line flag:

```bash
python main.py --topic "Artificial Intelligence in Renewable Energy"
```

You can also research multilingual topics (including Hindi):

```bash
python main.py --topic "भारत में सौर ऊर्जा का विकास"
```

---

## Configuration Guide (`config.py`)

All core parameters are organized in `config.py`. Here is a complete reference of each setting:

| Parameter | Default Value | Description |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `"gemini"` | Active AI provider. Set to `"gemini"` for cloud inference or `"local"` for local Ollama. |
| `GEMINI_MODEL` | `"gemini-3.5-flash-lite"` | Google Gemini model name. `gemini-3.5-flash-lite` provides high speed with minimal resource requirements. |
| `GEMINI_API_KEY` | Read from `.env` | Secret API key for Google AI Studio. Stored securely in `.env`. |
| `MODEL_NAME` | `"qwen3:1.7b"` | Name of the local Ollama model (e.g. `qwen3:1.7b` or `llama3.2:1b`). |
| `OLLAMA_HOST` | `"http://127.0.0.1:11434"` | URL address of the running Ollama server instance. |
| `MAX_TOKENS` | `512` | Maximum number of new tokens generated per LLM response. |
| `QUERIES_PER_TOPIC` | `2` | Number of distinct DuckDuckGo search queries formulated by the LLM. |
| `RESULTS_PER_QUERY` | `3` | Number of search results retrieved per DuckDuckGo query. |
| `PAGE_LIMIT` | `4` | Maximum number of web pages to visit and process during a full research run. |
| `CHAR_LIMIT_PER_PAGE` | `4000` | Maximum characters sent to the LLM per web page. Prevents token overflow and protects memory. |
| `REQUEST_DELAY_SECONDS`| `1.5` | Pause in seconds between web requests to respect web servers and avoid rate limits. |
| `REQUEST_TIMEOUT_SECONDS`| `10` | Maximum seconds to wait for a website to respond before timing out. |
| `USER_AGENT` | Polite bot string | Transparent HTTP header identifying your research crawler to webmasters. |
| `OUTPUT_DIR` | `BASE_DIR / "output"` | Directory where research reports and outputs are stored. |
| `EXPORT_PDF` | `True` | Automatically exports beautiful, styled PDF reports using ReportLab. |
| `EXPORT_DOCX` | `False` | When set to `True`, also exports reports as Microsoft Word (`.docx`) files. |

---

## Troubleshooting

### 1. Ollama Connection Error (`Failed to connect to Ollama at http://127.0.0.1:11434`)
- **Cause:** The Ollama service is not running on your computer.
- **Solution:**
  1. Open a new terminal and run:
     ```bash
     ollama serve
     ```
  2. Test connection by visiting `http://127.0.0.1:11434` in your browser (it should display *"Ollama is running"*).
  3. Ensure the model is downloaded:
     ```bash
     ollama list
     ollama pull qwen3:1.7b
     ```

### 2. Missing Gemini API Key (`Missing GEMINI_API_KEY`)
- **Cause:** `LLM_PROVIDER` is set to `"gemini"`, but no API key was found in `.env` or system environment variables.
- **Solution:**
  1. Get a free API key at [Google AI Studio](https://aistudio.google.com/).
  2. Create a `.env` file in the project folder with:
     ```env
     GEMINI_API_KEY=your_key_here
     ```
  3. Re-run `python main.py --test`.

### 3. Gemini Rate Limits (HTTP 429 / Resource Exhausted)
- **Cause:** Exceeding Google AI Studio's free tier requests-per-minute (RPM) limits.
- **Solution:**
  - The script features **automatic exponential backoff** (retrying after 2s, 4s, 8s, 16s).
  - To minimize API calls, keep `PAGE_LIMIT = 4` or decrease it in `config.py`.
  - Alternatively, switch to offline inference by setting `LLM_PROVIDER = "local"`.

### 4. Page Skipped (`Disallowed by robots.txt` or `HTTP 403 Forbidden`)
- **Cause:** The target website prohibits web scrapers or employs Cloudflare anti-bot verification.
- **Solution:** This is normal and expected crawler etiquette. The research agent automatically logs the skip in English and moves on to the next candidate link in the search queue.

### 5. DuckDuckGo Rate Limits or Empty Search Results
- **Cause:** Sending too many web search queries in rapid succession.
- **Solution:**
  - The project includes automatic fallback mechanisms between `ddgs` and `duckduckgo-search`.
  - If DuckDuckGo temporarily throttles your IP, wait 1–2 minutes before retrying, or increase `REQUEST_DELAY_SECONDS` in `config.py`.

### 6. High Memory (RAM) Usage on 4 GB Systems
- **Cause:** Running multiple heavy applications while executing local Ollama inference.
- **Solution:**
  - Switch to `LLM_PROVIDER = "gemini"` — running Gemini in the cloud offloads all model processing and consumes nearly 0 MB of local RAM.
  - If using Ollama locally, close heavy background apps (such as memory-intensive browser tabs).

---

## Educational Notes (`LEARNING.md`)

This project is built as an educational blueprint. Check out [LEARNING.md](file:///D:/Projects/Research%20Agent/LEARNING.md) for clear, beginner-friendly explanations and code examples covering 30 core Python and AI engineering concepts, including:
- Variables, Data Types, and Pathlib
- Functions, Guard Clauses, and Exception Handling (`try...except`)
- Provider Abstraction and Exponential Backoff
- Polite Web Crawling, URL Percent-Encoding, and HTML Parsing
- Memory-Safe Streaming Pipelines and Argument Parsing (`argparse`)
- File I/O (`with open(...)`), Context Managers, F-Strings, and Document Automation (`python-docx`)

---

## License

This project is open-source and free to use for personal, academic, and commercial exploration.
