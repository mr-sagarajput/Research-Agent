"""
LLM interaction module for the Free Research Agent.
Supports dual providers:
1. "gemini" -> Google AI Studio cloud API (Zero local RAM usage, fast, generous free tier)
2. "local"  -> Local Ollama models (100% offline, runs on your machine)

Exposes a unified query_llm() function so the rest of the agent never needs to care
which model backend is active.
"""

import os
import re
import time
from typing import Optional

from config import (
    LLM_PROVIDER,
    GEMINI_MODEL,
    GEMINI_API_KEY,
    MODEL_NAME,
    OLLAMA_HOST,
    MAX_TOKENS,
)


def remove_thinking_tags(text: str) -> str:
    """
    Removes <think>...</think> reasoning blocks from local model outputs.
    Some reasoning models output their internal scratchpad before the final answer.
    """
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return cleaned.strip()


def check_ollama_status() -> bool:
    """
    Checks if Ollama is running and the configured local model is installed.
    Prints helpful English instructions if either check fails.

    Returns:
        bool: True if ready, False otherwise.
    """
    try:
        import ollama
    except ImportError:
        print("[Error]: 'ollama' package is not installed. Run: pip install ollama")
        return False

    client = ollama.Client(host=OLLAMA_HOST)

    # Check 1: Is Ollama server reachable?
    try:
        response = client.list()
    except Exception:
        print("\n" + "=" * 60)
        print("[Ollama Connection Error]")
        print(f"Could not connect to Ollama at '{OLLAMA_HOST}'.")
        print("Please start the Ollama server by opening a terminal and running:")
        print("    ollama serve")
        print("=" * 60 + "\n")
        return False

    # Check 2: Is the model installed?
    installed_models = []
    models_list = getattr(response, "models", []) or response.get("models", [])
    for m in models_list:
        model_name = getattr(m, "model", None) or getattr(m, "name", None)
        if model_name:
            installed_models.append(model_name)

    model_found = any(
        m == MODEL_NAME or m.startswith(f"{MODEL_NAME}:") or MODEL_NAME.startswith(f"{m}:")
        for m in installed_models
    )

    if not model_found:
        print("\n" + "=" * 60)
        print("[Ollama Model Not Found]")
        print(f"Ollama is running, but the configured model '{MODEL_NAME}' is not installed.")
        print("\nTo resolve this:")
        print("1. See all currently installed models on your machine:")
        print("       ollama list")
        print(f"2. Download the required model (free, one-time download, no API key needed):")
        print(f"       ollama pull {MODEL_NAME}")
        print("=" * 60 + "\n")
        return False

    return True


def query_ollama(prompt: str, system_prompt: str = "") -> str:
    """
    Calls the local Ollama instance and strips <think> tags from output.
    """
    if not check_ollama_status():
        return ""

    try:
        import ollama
        client = ollama.Client(host=OLLAMA_HOST)
        options = {
            "num_predict": MAX_TOKENS,
            "temperature": 0.3,
        }
        response = client.generate(
            model=MODEL_NAME,
            prompt=prompt,
            system=system_prompt,
            options=options,
        )
        raw_text = response.get("response", "")
        # Strip thinking tags specifically for local models
        return remove_thinking_tags(raw_text)
    except Exception as error:
        print(f"[Error in Local Ollama]: {error}")
        return ""


def query_gemini(prompt: str, system_prompt: str = "") -> str:
    """
    Calls Google Gemini API with automatic retry on 429 (rate limit) errors.
    Uses exponential backoff: waits and retries up to 3 times before returning an error.
    Does NOT strip <think> tags.
    """
    if not GEMINI_API_KEY:
        print("\n" + "=" * 60)
        print("[Gemini API Key Missing]")
        print("No API key found in your .env file.")
        print("Please open '.env' and set your key like this:")
        print("    GEMINI_API_KEY=your_actual_api_key_here")
        print("=" * 60 + "\n")
        return ""

    try:
        from google import genai
    except ImportError:
        print("[Error]: 'google-genai' package is not installed. Run: pip install google-genai")
        return ""

    # Combine system prompt with main prompt if provided
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

    # Retry configuration for rate limits (429 errors)
    max_retries = 3
    retry_delay = 2  # initial wait time in seconds

    for attempt in range(1, max_retries + 1):
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=full_prompt,
            )
            # Successfully received response
            return (response.text or "").strip()

        except Exception as error:
            error_msg = str(error)

            # Check if this is a 429 Rate Limit error
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                if attempt < max_retries:
                    print(
                        f"[Gemini Rate Limit]: Hit 429 limit on attempt {attempt}/{max_retries}. "
                        f"Waiting {retry_delay} seconds before retry..."
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Double wait time for next retry (exponential backoff)
                    continue
                else:
                    print(
                        "\n[Gemini Rate Limit Exceeded]: Request failed after 3 retry attempts. "
                        "Google AI Studio rate limit reached. Please wait a minute and try again."
                    )
                    return ""
            else:
                # Other unexpected error (e.g. network disconnection, invalid model name)
                print(f"[Gemini Error]: API call failed. Details: {error_msg}")
                return ""

    return ""


def query_llm(prompt: str, system_prompt: str = "") -> str:
    """
    Unified entry point for the entire research agent.
    Routes the request to either Google Gemini or local Ollama based on LLM_PROVIDER in config.py.

    Parameters:
        prompt (str): The main question or text instruction for the model.
        system_prompt (str): Optional background instructions defining model behavior.

    Returns:
        str: Clean text produced by the active model, or empty string on failure.
    """
    if LLM_PROVIDER.lower() == "gemini":
        return query_gemini(prompt, system_prompt=system_prompt)
    else:
        return query_ollama(prompt, system_prompt=system_prompt)


if __name__ == "__main__":
    print("=" * 60)
    print("=== Testing LLM Module ===")
    print(f"Active Provider: {LLM_PROVIDER}")
    active_model = GEMINI_MODEL if LLM_PROVIDER.lower() == "gemini" else MODEL_NAME
    print(f"Active Model:    {active_model}")
    print("=" * 60)

    # Test 1: English Prompt
    test_english = "Explain in one simple sentence what a web crawler is."
    print(f"\n1. English Test Prompt:\n   '{test_english}'")
    reply_english = query_llm(test_english)
    print(f"\nResponse (from {active_model}):\n{reply_english}")

    # Test 2: Hindi Prompt
    test_hindi = "कृत्रिम बुद्धिमत्ता क्या है? एक सरल वाक्य में बताएं।"
    print(f"\n2. Hindi Test Prompt:\n   '{test_hindi}'")
    reply_hindi = query_llm(test_hindi)
    print(f"\nResponse (from {active_model}):\n{reply_hindi}")
    print("\n" + "=" * 60)
    print("Test finished successfully.")
