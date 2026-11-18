"""
Fetch and article extraction module for the Free Local Research Agent.
Downloads web pages safely, respects robots.txt permissions,
percent-encodes non-ASCII (Hindi) URLs, strips boilerplate/scripts,
truncates text to respect our 4 GB RAM budget, and logs every skip reason.
"""

import time
import threading
from urllib.parse import urlsplit, urlunsplit, quote, urlparse
import urllib.robotparser
from typing import Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

from config import (
    USER_AGENT,
    REQUEST_TIMEOUT_SECONDS,
    REQUEST_DELAY_SECONDS,
    CHAR_LIMIT_PER_PAGE,
)

# Thread-safe in-memory cache for robots.txt parsers to avoid redundant network round-trips
_robots_cache: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}
_robots_lock = threading.Lock()

# Thread-safe tracker for polite crawling delays per domain
_domain_last_request_time: Dict[str, float] = {}
_delay_lock = threading.Lock()


def clear_robots_cache() -> None:
    """Clears the cached robots.txt parsers (useful for testing or cache resets)."""
    with _robots_lock:
        _robots_cache.clear()


def reset_polite_delays() -> None:
    """Resets domain request timestamps (useful for testing or cache resets)."""
    with _delay_lock:
        _domain_last_request_time.clear()


def apply_polite_delay(url_or_domain: str, delay_seconds: float = REQUEST_DELAY_SECONDS) -> float:
    """
    Applies a non-blocking / elapsed-time polite crawling delay per domain.
    Only sleeps the remaining delta if the target domain was accessed more recently
    than delay_seconds ago. Different domains do not block each other.

    Parameters:
        url_or_domain (str): Full URL or domain netloc.
        delay_seconds (float): Required quiet period between requests to the same domain.

    Returns:
        float: Actual seconds slept (0.0 if no delay was required).
    """
    if delay_seconds <= 0:
        return 0.0

    domain = urlparse(url_or_domain).netloc if "://" in url_or_domain else url_or_domain
    if not domain:
        domain = "default"

    with _delay_lock:
        now = time.monotonic()
        last_time = _domain_last_request_time.get(domain, 0.0)
        elapsed = now - last_time
        sleep_needed = max(0.0, delay_seconds - elapsed)

    if sleep_needed > 0:
        time.sleep(sleep_needed)

    with _delay_lock:
        _domain_last_request_time[domain] = time.monotonic()

    return sleep_needed


def encode_url(url: str) -> str:
    """
    Percent-encodes non-ASCII characters in a URL (such as Hindi / Devanagari text).
    Standard HTTP requests require ASCII characters; this converts Unicode paths safely.
    Example: '.../wiki/कृत्रिम_बुद्धि' -> '.../wiki/%E0%A4%95%E0%A5%83...'
    """
    parts = urlsplit(url)
    # Safely quote the path, query, and fragment while keeping standard URL delimiter characters intact
    encoded_path = quote(parts.path, safe="/:@&=+$,-_.!~*'()")
    encoded_query = quote(parts.query, safe="/:@&=+$,-_.!~*'()?")
    encoded_fragment = quote(parts.fragment, safe="/:@&=+$,-_.!~*'()")
    return urlunsplit((parts.scheme, parts.netloc, encoded_path, encoded_query, encoded_fragment))


def is_allowed_by_robots(url: str, user_agent: str = USER_AGENT, use_cache: bool = True) -> bool:
    """
    Checks the website's robots.txt file to verify if automated crawling is permitted.
    Sends our custom User-Agent when retrieving robots.txt so servers that require
    a declared User-Agent respond properly.
    Uses thread-safe domain caching and safe connect/read timeouts to avoid redundant latency.

    Parameters:
        url (str): The web page URL to check.
        user_agent (str): The User-Agent identifier.
        use_cache (bool): Whether to check and update the domain robots cache.

    Returns:
        bool: True if allowed (or if robots.txt is missing/inaccessible), False if forbidden.
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if not domain:
            return True

        if use_cache:
            with _robots_lock:
                if domain in _robots_cache:
                    cached_rp = _robots_cache[domain]
                    if cached_rp is None:
                        # Cached as missing / open (404 or failed earlier)
                        return True
                    return cached_rp.can_fetch(user_agent, url)

        robots_url = f"{parsed.scheme or 'https'}://{domain}/robots.txt"
        headers = {"User-Agent": user_agent}

        # Safe connection and read timeout (3.0s connect, 5.0s read)
        timeout = (3.0, min(5.0, float(REQUEST_TIMEOUT_SECONDS)))
        response = requests.get(robots_url, headers=headers, timeout=timeout)

        # If robots.txt doesn't exist (404), crawling is permitted
        if response.status_code == 404:
            if use_cache:
                with _robots_lock:
                    _robots_cache[domain] = None
            return True

        if response.status_code == 200:
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(response.text.splitlines())
            if use_cache:
                with _robots_lock:
                    _robots_cache[domain] = rp
            return rp.can_fetch(user_agent, url)

        # If any other status code, allow by default and cache as open
        if use_cache:
            with _robots_lock:
                _robots_cache[domain] = None
        return True
    except Exception:
        # If robots.txt cannot be accessed or times out, allow crawling
        return True


def fetch_article_text(
    url: str,
    respect_delay: bool = True,
    delay_seconds: float = REQUEST_DELAY_SECONDS,
) -> Optional[str]:
    """
    Downloads a web page, verifies robots.txt, extracts readable main text,
    and truncates it to CHAR_LIMIT_PER_PAGE.
    Uses per-domain non-blocking polite delays and safe connect/read timeouts.

    Parameters:
        url (str): Web page URL to fetch.
        respect_delay (bool): Whether to enforce the polite crawl delay.
        delay_seconds (float): Custom delay period in seconds.

    Returns:
        Optional[str]: Clean article text string, or None if skipped/failed.
    """
    clean_url = url.strip()
    if not clean_url:
        print("[Fetch Skip]: Empty URL provided.")
        return None

    # Step 1: Ensure URL is properly encoded for non-ASCII characters (e.g. Hindi)
    try:
        encoded_target_url = encode_url(clean_url)
    except Exception as error:
        print(f"[Fetch Skip]: Could not encode URL '{clean_url}'. Reason: {error}")
        return None

    # Step 2: Check robots.txt permissions
    if not is_allowed_by_robots(encoded_target_url, USER_AGENT):
        print(f"[Fetch Skip]: Crawling forbidden by robots.txt for '{clean_url}'")
        return None

    # Step 3: Polite crawling delay (non-blocking per-domain: sleeps only remaining delta if needed)
    if respect_delay:
        apply_polite_delay(encoded_target_url, delay_seconds=delay_seconds)

    # Step 4: Perform HTTP GET request with safe timeout handling
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    }

    try:
        # Dual safe timeout: max 3.05s connect, REQUEST_TIMEOUT_SECONDS read
        connect_timeout = min(3.05, float(REQUEST_TIMEOUT_SECONDS))
        read_timeout = float(REQUEST_TIMEOUT_SECONDS)

        response = requests.get(
            encoded_target_url,
            headers=headers,
            timeout=(connect_timeout, read_timeout),
            allow_redirects=True,
        )

        # Check HTTP status code
        if response.status_code != 200:
            print(f"[Fetch Skip]: HTTP status {response.status_code} for '{clean_url}'")
            return None

        # Check content type (must be HTML)
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            print(f"[Fetch Skip]: Non-HTML content type '{content_type}' for '{clean_url}'")
            return None

        # Step 5: Parse HTML and extract clean text
        soup = BeautifulSoup(response.text, "html.parser")

        # 5a. Remove standard clutter tags (scripts, styles, navigation, headers, footers)
        for element in soup(["script", "style", "noscript", "header", "footer", "nav", "svg", "form", "aside"]):
            element.decompose()

        # 5b. Remove Wikipedia maintenance banners, editor notices, sidebars, and navigation clutter
        clutter_selectors = [
            ".ambox",           # Article message boxes (e.g. translation/cleanup warnings)
            ".tmbox",           # Talk page message boxes
            ".cmbox",           # Category message boxes
            ".imbox",           # Image message boxes
            ".mbox-small",      # Compact maintenance boxes
            ".navbox",          # Navigation footers and templates
            ".vertical-navbox", # Side navigation templates
            ".sidebar",         # Generic sidebars
            ".mw-editsection",  # [edit] section links
            ".mw-jump-link",    # "Jump to content" skip links
            ".mw-indicators",   # Top-corner icons
            ".catlinks",        # Category link footers
            ".hatnote",         # "For other uses, see..." disambiguation notes
            ".reference",       # Footnote superscripts [1], [2]
            ".reflist",         # Reference list sections
            "#siteNotice",      # Fundraiser/announcement banners
            "#toc",             # Table of contents boxes
        ]
        for selector in clutter_selectors:
            for element in soup.select(selector):
                element.decompose()

        # Extract textual content
        text = soup.get_text(separator=" ", strip=True)

        # Clean up excess whitespace
        words = text.split()
        clean_text = " ".join(words)

        # Check if meaningful text was found
        if len(clean_text) < 120:
            print(f"[Fetch Skip]: Content too short ({len(clean_text)} characters) for '{clean_url}'")
            return None

        # Step 6: Truncate to memory-safe limit (protects 4 GB RAM)
        if len(clean_text) > CHAR_LIMIT_PER_PAGE:
            clean_text = clean_text[:CHAR_LIMIT_PER_PAGE]

        return clean_text

    except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, requests.exceptions.Timeout):
        print(f"[Fetch Skip]: Request timed out after {REQUEST_TIMEOUT_SECONDS}s for '{clean_url}'")
        return None
    except requests.exceptions.RequestException as error:
        print(f"[Fetch Skip]: Network error for '{clean_url}'. Reason: {error}")
        return None
    except Exception as error:
        print(f"[Fetch Skip]: Unexpected error parsing '{clean_url}'. Reason: {error}")
        return None


def fetch_multiple_articles(
    urls: List[str],
    max_workers: int = 3,
    respect_delay: bool = True,
) -> Dict[str, Optional[str]]:
    """
    Concurrently fetches multiple web pages using a thread pool.
    Polite crawling delays are enforced per-domain so that requests to different
    domains execute concurrently without delay, while requests to the same domain
    respect politeness.

    Parameters:
        urls (List[str]): List of URLs to fetch.
        max_workers (int): Maximum worker threads (default 3 to keep RAM usage low).
        respect_delay (bool): Whether to enforce polite delays.

    Returns:
        Dict[str, Optional[str]]: Mapping from URL to clean article text (or None if failed).
    """
    results: Dict[str, Optional[str]] = {}
    if not urls:
        return results

    # Deduplicate while preserving order
    unique_urls = list(dict.fromkeys([u.strip() for u in urls if u.strip()]))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(fetch_article_text, url, respect_delay=respect_delay): url
            for url in unique_urls
        }
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                results[url] = future.result()
            except Exception as err:
                print(f"[Fetch Concurrent Error]: Error fetching {url}: {err}")
                results[url] = None

    return results


if __name__ == "__main__":
    print("=== Testing Fetch Module ===")

    # Test 1: English URL
    en_url = "https://en.wikipedia.org/wiki/Python_(programming_language)"
    print(f"\n1. Fetching English URL:\n   {en_url}")
    en_text = fetch_article_text(en_url)
    if en_text:
        print(f"   [Success] Extracted {len(en_text)} characters.")
        print(f"   Snippet: {en_text[:180]}...")
    else:
        print("   [Failed] Could not fetch English URL.")

    # Test 2: Hindi URL (Unicode non-ASCII URL)
    hi_url = "https://hi.wikipedia.org/wiki/कृत्रिम_बुद्धि"
    print(f"\n2. Fetching Hindi URL:\n   {hi_url}")
    hi_text = fetch_article_text(hi_url)
    if hi_text:
        print(f"   [Success] Extracted {len(hi_text)} characters.")
        print(f"   Snippet: {hi_text[:180]}...")
    else:
        print("   [Failed] Could not fetch Hindi URL.")
