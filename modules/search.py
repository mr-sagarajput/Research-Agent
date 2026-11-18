"""
Search module for the Free Local Research Agent.
Performs free web searches using the ddgs package (with duckduckgo-search as fallback),
extracting page titles and URLs without requiring any API keys.
Skips unsupported formats such as PDF files and video platforms (YouTube).
"""

import time
from typing import List, Dict, Tuple

# Attempt to import ddgs first, fallback to duckduckgo_search if needed
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

from config import RESULTS_PER_QUERY, REQUEST_DELAY_SECONDS, QUERIES_PER_TOPIC
from modules.llm import query_llm


def deduplicate_search_results(results: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Deduplicates a list of search result dictionaries by URL using a set,
    preserving the original discovery order and ignoring duplicate or empty links.

    Parameters:
        results: List of result dicts, each with 'url' and 'title'.

    Returns:
        List[Dict[str, str]]: List of unique result dicts.
    """
    seen_urls = set()
    unique_results: List[Dict[str, str]] = []

    for item in results:
        url = item.get("url", "").strip()
        if not url:
            continue
        norm_url = url.rstrip("/")
        if norm_url not in seen_urls:
            seen_urls.add(norm_url)
            unique_results.append(item)

    return unique_results


def is_supported_article_url(url: str) -> Tuple[bool, str]:
    """
    Checks if a URL points to a standard readable HTML web page.
    Filters out PDF files and YouTube video links.

    Returns:
        Tuple[bool, str]: (True, "") if supported, or (False, reason) if skipped.
    """
    lower_url = url.lower()

    if "youtube.com" in lower_url or "youtu.be" in lower_url:
        return False, "YouTube video link (cannot extract HTML article text)"

    if lower_url.endswith(".pdf") or ".pdf?" in lower_url or ".pdf#" in lower_url:
        return False, "PDF binary file (not an HTML web page)"

    return True, ""


def search_web(query: str, max_results: int = RESULTS_PER_QUERY) -> List[Dict[str, str]]:
    """
    Searches DuckDuckGo for a given text query and returns a list of result dictionaries.
    Applies REQUEST_DELAY_SECONDS before requesting to avoid rate limits.
    Skips PDF files and YouTube links, logging the reason for each skipped item.

    Parameters:
        query (str): The search phrase to look up.
        max_results (int): Maximum number of search results to return.

    Returns:
        List[Dict[str, str]]: A list of dictionaries, each containing 'title' and 'url'.
                              Example: [{'title': '...', 'url': 'https://...'}]
    """
    results: List[Dict[str, str]] = []

    # Strip whitespace from query
    clean_query = query.strip()
    if not clean_query:
        print("[Search Warning]: Empty query provided. Skipping search.")
        return results

    try:
        # Pause briefly to be polite and avoid rate limits (configured in config.py)
        time.sleep(REQUEST_DELAY_SECONDS)

        # Create DDGS search instance and run text search
        with DDGS() as ddgs:
            # Request extra items to allow for filtered/skipped URLs
            search_generator = ddgs.text(clean_query, max_results=max_results + 3)
            for item in search_generator:
                if len(results) >= max_results:
                    break

                title = item.get("title", "No Title")
                # ddgs returns URL in 'href' or 'url'
                url = item.get("href") or item.get("url", "")
                
                # Check for valid web link
                if not url or not (url.startswith("http://") or url.startswith("https://")):
                    continue

                # Filter out PDFs and YouTube links
                supported, reason = is_supported_article_url(url)
                if not supported:
                    print(f"[Search Skip]: Skipping '{url}' -> Reason: {reason}")
                    continue

                results.append({
                    "title": title,
                    "url": url
                })

    except Exception as error:
        print(f"[Search Error]: Failed to retrieve results for '{clean_query}'. Details: {error}")

    return results


def generate_search_queries(topic: str, num_queries: int = QUERIES_PER_TOPIC) -> List[str]:
    """
    Uses the local LLM to generate 2-3 concise search engine queries for a given research topic.
    If the LLM fails or returns unparseable text, falls back to using the raw topic itself.

    Parameters:
        topic (str): The research subject.
        num_queries (int): How many queries to create.

    Returns:
        List[str]: A list of clean search query strings.
    """
    system_instruction = (
        "You are a helpful research query generator. "
        "Generate short, highly relevant web search queries. "
        "Output ONLY the queries, one per line, with no numbers, bullet points, or commentary."
    )
    prompt = (
        f"Generate {num_queries} distinct, short search queries to research this topic: '{topic}'\n"
        f"Return exactly {num_queries} lines. One query per line."
    )

    llm_output = query_llm(prompt, system_prompt=system_instruction)

    # Process each line from the model
    queries = []
    for line in llm_output.splitlines():
        # Remove numbers like '1.', bullets '-', or quotes
        clean_line = line.strip().lstrip("0123456789.-*• ").strip('"\',')
        if clean_line and len(clean_line) > 3:
            queries.append(clean_line)

    # Take up to requested count
    queries = queries[:num_queries]

    # Fallback: if model produced nothing usable, use the original topic as the query
    if not queries:
        queries = [topic.strip()]

    return queries


if __name__ == "__main__":
    print("=== Testing Search Module with Filtering ===")

    # Test with queries likely to surface PDFs or YouTube videos to verify filtering
    filter_test_query = "Python tutorial pdf youtube"
    print(f"\n1. Testing Filtering on: '{filter_test_query}'")
    test_results = search_web(filter_test_query, max_results=3)
    print(f"Accepted results count: {len(test_results)}")
    for idx, res in enumerate(test_results, 1):
        print(f"   [{idx}] {res['title']}")
        print(f"       URL: {res['url']}")
