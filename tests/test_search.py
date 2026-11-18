"""
Unit tests for modules/search.py:
- is_supported_article_url (filtering YouTube videos, PDF binaries, and keeping valid HTML articles)
- deduplicate_search_results (set-based URL deduplication, preserving discovery order)
- generate_search_queries (parsing LLM responses, stripping formatting, fallback on failure)
- search_web (empty query handling, DDGS search integration, error handling)
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.search import (
    is_supported_article_url,
    deduplicate_search_results,
    generate_search_queries,
    search_web,
)


class TestURLFiltering(unittest.TestCase):
    """Tests URL filtering for unsupported media types (YouTube, PDF)."""

    def test_valid_html_article_urls(self):
        valid_urls = [
            "https://en.wikipedia.org/wiki/Artificial_intelligence",
            "https://news.ycombinator.com/item?id=12345",
            "https://blog.example.org/2026/01/future-of-python.html",
            "http://example.com/path/to/resource",
        ]
        for url in valid_urls:
            supported, reason = is_supported_article_url(url)
            self.assertTrue(supported, f"URL should be supported: {url}")
            self.assertEqual(reason, "")

    def test_unsupported_youtube_urls(self):
        yt_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://youtube.com/v/dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=abc123",
        ]
        for url in yt_urls:
            supported, reason = is_supported_article_url(url)
            self.assertFalse(supported, f"YouTube URL should be rejected: {url}")
            self.assertIn("YouTube", reason)

    def test_unsupported_pdf_urls(self):
        pdf_urls = [
            "https://arxiv.org/pdf/1706.03762.pdf",
            "https://example.com/whitepaper.pdf?version=2",
            "https://docs.example.org/spec.pdf#page=12",
            "https://data.gov/report.PDF",
        ]
        for url in pdf_urls:
            supported, reason = is_supported_article_url(url)
            self.assertFalse(supported, f"PDF URL should be rejected: {url}")
            self.assertIn("PDF", reason)


class TestSearchDeduplication(unittest.TestCase):
    """Tests set-based deduplication of search results while preserving discovery order."""

    def test_deduplicate_results_with_duplicates(self):
        raw_items = [
            {"title": "Article 1", "url": "https://example.com/ai-intro"},
            {"title": "Article 2", "url": "https://example.com/ml-basics"},
            {"title": "Duplicate Article 1", "url": "https://example.com/ai-intro"},
            {"title": "Article 1 with Trailing Slash", "url": "https://example.com/ai-intro/"},
            {"title": "Article 3", "url": "https://example.com/deep-learning"},
        ]

        deduped = deduplicate_search_results(raw_items)
        self.assertEqual(len(deduped), 3)

        # Discovery order must be preserved
        expected_urls = [
            "https://example.com/ai-intro",
            "https://example.com/ml-basics",
            "https://example.com/deep-learning",
        ]
        self.assertEqual([item["url"] for item in deduped], expected_urls)

        # First title encountered should be retained
        self.assertEqual(deduped[0]["title"], "Article 1")

    def test_deduplicate_results_empty_and_whitespace_urls(self):
        raw_items = [
            {"title": "No URL 1", "url": ""},
            {"title": "Valid", "url": "https://example.com/page"},
            {"title": "Whitespace URL", "url": "   "},
            {"title": "Missing URL Key"},
        ]
        deduped = deduplicate_search_results(raw_items)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["url"], "https://example.com/page")

    def test_deduplicate_results_empty_list(self):
        self.assertEqual(deduplicate_search_results([]), [])


class TestGenerateSearchQueries(unittest.TestCase):
    """Tests query generation parsing, formatting cleanup, and graceful fallbacks."""

    @patch("modules.search.query_llm")
    def test_generate_queries_success(self, mock_query_llm):
        mock_query_llm.return_value = (
            '1. "solar cell efficiency breakthroughs 2026"\n'
            '- perovskite photovoltaic commercial developments\n'
            '3. * next generation solar panels research *\n'
        )
        queries = generate_search_queries("Solar Energy", num_queries=2)

        self.assertEqual(len(queries), 2)
        # Should strip numbering, bullets, quotes, and asterisks
        self.assertEqual(queries[0], "solar cell efficiency breakthroughs 2026")
        self.assertEqual(queries[1], "perovskite photovoltaic commercial developments")

    @patch("modules.search.query_llm", return_value="")
    def test_generate_queries_fallback_on_empty_llm_output(self, mock_query_llm):
        """When LLM returns empty string, falls back to raw topic."""
        topic = "Quantum Computing in Cryptography"
        queries = generate_search_queries(topic, num_queries=2)

        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0], topic)

    @patch("modules.search.query_llm")
    def test_generate_queries_fallback_on_unparseable_output(self, mock_query_llm):
        """When LLM returns only punctuation or short artifacts, falls back to raw topic."""
        mock_query_llm.return_value = "---\n..\n* \n"
        topic = "CRISPR Gene Editing"
        queries = generate_search_queries(topic, num_queries=3)

        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0], topic)


class TestSearchWeb(unittest.TestCase):
    """Tests web searching via DuckDuckGo and error resilience."""

    def test_search_web_empty_query(self):
        self.assertEqual(search_web(""), [])
        self.assertEqual(search_web("   "), [])

    @patch("modules.search.time.sleep")
    @patch("modules.search.DDGS")
    def test_search_web_success_and_filtering(self, mock_ddgs_cls, mock_sleep):
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = [
            {"title": "Valid Article A", "href": "https://tech.org/ai-breakthrough"},
            {"title": "YouTube Video", "href": "https://youtube.com/watch?v=123"},
            {"title": "PDF Document", "href": "https://paper.edu/research.pdf"},
            {"title": "Valid Article B", "url": "https://science.org/ml-future"},
        ]
        # Context manager support: with DDGS() as ddgs:
        mock_ddgs_cls.return_value.__enter__.return_value = mock_ddgs_instance

        results = search_web("artificial intelligence", max_results=2)

        # YouTube and PDF must be skipped; only valid HTML links retained up to max_results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["title"], "Valid Article A")
        self.assertEqual(results[0]["url"], "https://tech.org/ai-breakthrough")
        self.assertEqual(results[1]["title"], "Valid Article B")
        self.assertEqual(results[1]["url"], "https://science.org/ml-future")

    @patch("modules.search.time.sleep")
    @patch("modules.search.DDGS")
    def test_search_web_exception_handling(self, mock_ddgs_cls, mock_sleep):
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.side_effect = Exception("DuckDuckGo rate limit or network unreachable")
        mock_ddgs_cls.return_value.__enter__.return_value = mock_ddgs_instance

        results = search_web("query that errors out", max_results=3)
        # Should gracefully return empty list without raising
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
