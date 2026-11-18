"""
Unit tests for modules/fetch.py:
- URL percent-encoding (Devanagari / Hindi & ASCII)
- robots.txt permissions, caching, and fallback handling
- Polite crawling logic (adaptive / non-blocking per-domain delay)
- HTML element decomposition (<script>, <style>, <nav>, Wikipedia clutter)
- Memory character limit truncation & short-content filtering
- Safe timeout and network exception handling
- Concurrency / multi-article fetching
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import requests

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import CHAR_LIMIT_PER_PAGE
from modules.fetch import (
    encode_url,
    is_allowed_by_robots,
    fetch_article_text,
    apply_polite_delay,
    clear_robots_cache,
    reset_polite_delays,
    fetch_multiple_articles,
)


class TestURLEncoding(unittest.TestCase):
    """Tests URL percent-encoding for ASCII and non-ASCII (Hindi/Devanagari) characters."""

    def test_encode_url_devanagari_hindi(self):
        hindi_url = "https://hi.wikipedia.org/wiki/कृत्रिम_बुद्धि"
        encoded = encode_url(hindi_url)
        # Should be valid ASCII string
        self.assertTrue(encoded.isascii())
        # Should contain percent-encoded bytes for Hindi characters
        self.assertIn("%E0%A4%", encoded)
        self.assertTrue(encoded.startswith("https://hi.wikipedia.org/wiki/"))

    def test_encode_url_ascii_unchanged(self):
        ascii_url = "https://en.wikipedia.org/wiki/Python_(programming_language)"
        encoded = encode_url(ascii_url)
        self.assertEqual(encoded, ascii_url)

    def test_encode_url_with_query_and_fragment(self):
        complex_url = "https://example.com/खोज?q=मशीन_लर्निंग#निष्कर्ष"
        encoded = encode_url(complex_url)
        self.assertTrue(encoded.isascii())
        self.assertIn("%E0%A4%", encoded)
        self.assertTrue(encoded.startswith("https://example.com/"))
        self.assertIn("?", encoded)
        self.assertIn("#", encoded)


class TestRobotsTxtValidator(unittest.TestCase):
    """Tests robots.txt parsing, caching, and graceful failure fallbacks."""

    def setUp(self):
        clear_robots_cache()

    def tearDown(self):
        clear_robots_cache()

    @patch("modules.fetch.requests.get")
    def test_is_allowed_by_robots_permitted(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nAllow: /articles/\nDisallow: /admin/"
        mock_get.return_value = mock_response

        allowed = is_allowed_by_robots("https://example.com/articles/ai-research")
        self.assertTrue(allowed)
        mock_get.assert_called_once()

    @patch("modules.fetch.requests.get")
    def test_is_allowed_by_robots_disallowed(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nDisallow: /private/\nDisallow: /secret.html"
        mock_get.return_value = mock_response

        allowed = is_allowed_by_robots("https://example.com/private/data")
        self.assertFalse(allowed)

    @patch("modules.fetch.requests.get")
    def test_is_allowed_by_robots_404_missing(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        allowed = is_allowed_by_robots("https://nobots.example.org/page")
        self.assertTrue(allowed)

    @patch("modules.fetch.requests.get")
    def test_is_allowed_by_robots_timeout_fallback(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
        allowed = is_allowed_by_robots("https://slowserver.org/article")
        # Ethical fallback: default to allow on network timeout
        self.assertTrue(allowed)

    @patch("modules.fetch.requests.get")
    def test_is_allowed_by_robots_connection_error_fallback(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("Host unreachable")
        allowed = is_allowed_by_robots("https://broken.invalid/article")
        self.assertTrue(allowed)

    @patch("modules.fetch.requests.get")
    def test_is_allowed_by_robots_domain_caching(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nDisallow: /blocked/"
        mock_get.return_value = mock_response

        # First call fetches robots.txt
        res1 = is_allowed_by_robots("https://cached-site.com/page1")
        # Second call to same domain should use cached parser
        res2 = is_allowed_by_robots("https://cached-site.com/page2")

        self.assertTrue(res1)
        self.assertTrue(res2)
        # requests.get should only have been called ONCE due to domain cache
        self.assertEqual(mock_get.call_count, 1)

    def test_is_allowed_by_robots_empty_domain(self):
        # Malformed URL without domain should return True safely
        self.assertTrue(is_allowed_by_robots("/relative/path"))


class TestPoliteCrawlingLogic(unittest.TestCase):
    """Tests non-blocking, adaptive per-domain polite crawling delays."""

    def setUp(self):
        reset_polite_delays()

    def tearDown(self):
        reset_polite_delays()

    def test_apply_polite_delay_first_call_non_blocking(self):
        # The very first request to a domain should not block (0s slept)
        slept = apply_polite_delay("https://example1.com/test", delay_seconds=1.5)
        self.assertEqual(slept, 0.0)

    def test_apply_polite_delay_different_domains_do_not_block(self):
        # Request to domain A
        slept_a = apply_polite_delay("https://alpha.org/page1", delay_seconds=2.0)
        # Immediate request to domain B should NOT wait for domain A's delay
        slept_b = apply_polite_delay("https://beta.com/page2", delay_seconds=2.0)
        self.assertEqual(slept_a, 0.0)
        self.assertEqual(slept_b, 0.0)

    @patch("modules.fetch.time.sleep")
    def test_apply_polite_delay_subsequent_request_same_domain(self, mock_sleep):
        # First call: no wait
        apply_polite_delay("https://gamma.com/page1", delay_seconds=1.5)
        mock_sleep.assert_not_called()

        # Second call to same domain immediately after: should sleep remaining time
        slept = apply_polite_delay("https://gamma.com/page2", delay_seconds=1.5)
        self.assertGreater(slept, 0.0)
        mock_sleep.assert_called_once()

    def test_apply_polite_delay_zero_delay(self):
        slept = apply_polite_delay("https://delta.com/page", delay_seconds=0)
        self.assertEqual(slept, 0.0)


class TestFetchArticleText(unittest.TestCase):
    """Tests web page fetching, HTML decomposition, truncation, and safety guards."""

    def setUp(self):
        clear_robots_cache()
        reset_polite_delays()

    def tearDown(self):
        clear_robots_cache()
        reset_polite_delays()

    def test_fetch_article_text_empty_url(self):
        self.assertIsNone(fetch_article_text(""))
        self.assertIsNone(fetch_article_text("   "))

    @patch("modules.fetch.is_allowed_by_robots", return_value=False)
    def test_fetch_article_text_robots_forbidden(self, mock_robots):
        result = fetch_article_text("https://example.com/forbidden", respect_delay=False)
        self.assertIsNone(result)

    @patch("modules.fetch.is_allowed_by_robots", return_value=True)
    @patch("modules.fetch.requests.get")
    def test_fetch_article_text_http_error(self, mock_get, mock_robots):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response

        result = fetch_article_text("https://example.com/denied", respect_delay=False)
        self.assertIsNone(result)

    @patch("modules.fetch.is_allowed_by_robots", return_value=True)
    @patch("modules.fetch.requests.get")
    def test_fetch_article_text_non_html_skipped(self, mock_get, mock_robots):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/pdf"}
        mock_get.return_value = mock_response

        result = fetch_article_text("https://example.com/document.pdf", respect_delay=False)
        self.assertIsNone(result)

    @patch("modules.fetch.is_allowed_by_robots", return_value=True)
    @patch("modules.fetch.requests.get")
    def test_fetch_article_text_html_decomposition(self, mock_get, mock_robots):
        """Verifies stripping of <script>, <style>, <nav>, and clutter classes."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>body { color: red; }</style>
            <script>alert('malicious track script');</script>
        </head>
        <body>
            <header><h1>Site Header Navigation</h1></header>
            <nav><a href="/home">Home</a><a href="/news">News</a></nav>
            <aside>Ad banner and sponsorship links</aside>
            <div id="siteNotice">Important site banner notice!</div>
            <div id="toc"><h2>Table of Contents</h2><ul><li>Section 1</li></ul></div>
            <div class="hatnote">For other uses, see AI (disambiguation).</div>
            <div class="navbox">Wiki navigation footer table</div>
            <div class="sidebar">Sidebar navigational menu</div>

            <main>
                <article>
                    <p>
                        Artificial intelligence represents an interdisciplinary field of computer science
                        dedicated to developing algorithms that can perceive their environment, reason through complex
                        challenges, and solve diverse technical problems without explicit rule programming.
                    </p>
                    <sup class="reference">[1]</sup>
                    <span class="mw-editsection">[edit]</span>
                    <p>
                        Recent advancements in transformer architectures and deep generative neural networks have
                        dramatically accelerated automation across healthcare, scientific research, and enterprise software.
                    </p>
                </article>
            </main>

            <footer><p>Copyright 2026. All rights reserved.</p></footer>
        </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_response.text = html_content
        mock_get.return_value = mock_response

        result = fetch_article_text("https://example.com/ai-article", respect_delay=False)
        self.assertIsNotNone(result)

        # Decomposed tags must NOT be present
        self.assertNotIn("malicious track script", result)
        self.assertNotIn("color: red", result)
        self.assertNotIn("Site Header Navigation", result)
        self.assertNotIn("Ad banner", result)
        self.assertNotIn("Important site banner notice", result)
        self.assertNotIn("Table of Contents", result)
        self.assertNotIn("AI (disambiguation)", result)
        self.assertNotIn("Wiki navigation footer", result)
        self.assertNotIn("Copyright 2026", result)
        self.assertNotIn("[edit]", result)
        self.assertNotIn("[1]", result)

        # Core informative text MUST be present
        self.assertIn("Artificial intelligence represents an interdisciplinary field", result)
        self.assertIn("advancements in transformer architectures", result)

    @patch("modules.fetch.is_allowed_by_robots", return_value=True)
    @patch("modules.fetch.requests.get")
    def test_fetch_article_text_short_content_skipped(self, mock_get, mock_robots):
        """Content shorter than 120 chars should be skipped as low-value/empty."""
        short_html = "<html><body><p>Short paragraph with minimal content.</p></body></html>"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.text = short_html
        mock_get.return_value = mock_response

        result = fetch_article_text("https://example.com/stub", respect_delay=False)
        self.assertIsNone(result)

    @patch("modules.fetch.is_allowed_by_robots", return_value=True)
    @patch("modules.fetch.requests.get")
    def test_fetch_article_text_truncation_limit(self, mock_get, mock_robots):
        """Verifies text longer than CHAR_LIMIT_PER_PAGE is truncated to protect memory."""
        long_paragraph = "Python is a modern high-level programming language designed for productivity. " * 150
        html_content = f"<html><body><p>{long_paragraph}</p></body></html>"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.text = html_content
        mock_get.return_value = mock_response

        result = fetch_article_text("https://example.com/long-page", respect_delay=False)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), CHAR_LIMIT_PER_PAGE)

    @patch("modules.fetch.is_allowed_by_robots", return_value=True)
    @patch("modules.fetch.requests.get")
    def test_fetch_article_text_timeout_handling(self, mock_get, mock_robots):
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
        result = fetch_article_text("https://example.com/hanging", respect_delay=False)
        self.assertIsNone(result)

    @patch("modules.fetch.is_allowed_by_robots", return_value=True)
    @patch("modules.fetch.requests.get")
    def test_fetch_article_text_network_error(self, mock_get, mock_robots):
        mock_get.side_effect = requests.exceptions.ConnectionError("DNS failure")
        result = fetch_article_text("https://invalid-nonexistent-domain.xyz", respect_delay=False)
        self.assertIsNone(result)


class TestConcurrentFetching(unittest.TestCase):
    """Tests multi-threaded concurrent page fetching utility."""

    def test_fetch_multiple_articles_empty(self):
        results = fetch_multiple_articles([])
        self.assertEqual(results, {})

    @patch("modules.fetch.fetch_article_text")
    def test_fetch_multiple_articles_concurrent(self, mock_fetch):
        def side_effect_fetch(url, **kwargs):
            if "fail" in url:
                return None
            return f"Article text for {url} containing enough text to qualify as valid content."

        mock_fetch.side_effect = side_effect_fetch

        urls = [
            "https://site-a.com/page1",
            "https://site-b.com/page2",
            "https://site-fail.com/broken",
        ]
        results = fetch_multiple_articles(urls, max_workers=2, respect_delay=False)

        self.assertEqual(len(results), 3)
        self.assertIn("https://site-a.com/page1", results)
        self.assertIn("https://site-b.com/page2", results)
        self.assertIn("Article text for https://site-a.com/page1", results["https://site-a.com/page1"])
        self.assertIsNone(results["https://site-fail.com/broken"])


if __name__ == "__main__":
    unittest.main()
