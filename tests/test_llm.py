"""
Unit tests for modules/llm.py:
- remove_thinking_tags regex (single block, multiline, multiple blocks, clean text, empty text)
- Guard clauses (missing API keys, missing libraries, offline Ollama status)
- Fallback and error recovery (Gemini 429 rate limit retries with exponential backoff, fatal errors)
- Provider routing (query_llm dispatching to Gemini or Ollama)
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.llm import (
    remove_thinking_tags,
    check_ollama_status,
    query_ollama,
    query_gemini,
    query_llm,
)


class TestRemoveThinkingTags(unittest.TestCase):
    """Tests stripping <think>...</think> reasoning blocks from model outputs."""

    def test_single_line_thinking_block(self):
        raw = "<think>Let me formulate the answer step by step.</think>The capital of France is Paris."
        expected = "The capital of France is Paris."
        self.assertEqual(remove_thinking_tags(raw), expected)

    def test_multiline_thinking_block(self):
        raw = """<think>
        Step 1: Parse user request.
        Step 2: Synthesize findings.
        Step 3: Draft response.
        </think>
        Renewable energy is essential for sustainable development."""
        expected = "Renewable energy is essential for sustainable development."
        self.assertEqual(remove_thinking_tags(raw), expected)

    def test_multiple_thinking_blocks(self):
        raw = "<think>Thought 1</think>Part A.<think>Thought 2</think>Part B."
        result = remove_thinking_tags(raw)
        self.assertEqual(result, "Part A.Part B.")

    def test_no_thinking_tags_present(self):
        raw = "This is a clean direct response with no internal reasoning tags."
        self.assertEqual(remove_thinking_tags(raw), raw)

    def test_empty_and_whitespace_input(self):
        self.assertEqual(remove_thinking_tags(""), "")
        self.assertEqual(remove_thinking_tags("   \n\t  "), "")

    def test_thinking_tag_with_trailing_spaces(self):
        raw = "  <think>Scratchpad notes</think>  Final result.   "
        self.assertEqual(remove_thinking_tags(raw), "Final result.")


class TestLLMGuardClauses(unittest.TestCase):
    """Tests guard clauses for missing credentials, offline servers, and missing packages."""

    @patch("modules.llm.GEMINI_API_KEY", "")
    def test_query_gemini_missing_api_key_guard(self):
        # Should return empty string without attempting network call
        result = query_gemini("Test prompt")
        self.assertEqual(result, "")

    def test_query_gemini_missing_package_guard(self):
        with patch.dict(sys.modules, {"google.genai": None}):
            with patch("modules.llm.GEMINI_API_KEY", "fake_key_123"):
                result = query_gemini("Test prompt")
                self.assertEqual(result, "")

    @patch("modules.llm.check_ollama_status", return_value=False)
    def test_query_ollama_offline_guard(self, mock_status):
        result = query_ollama("Test prompt")
        self.assertEqual(result, "")
        mock_status.assert_called_once()

    def test_check_ollama_status_package_not_installed(self):
        with patch.dict(sys.modules, {"ollama": None}):
            result = check_ollama_status()
            self.assertEqual(result, False)

    def test_check_ollama_status_connection_failure(self):
        mock_ollama = MagicMock()
        mock_client = MagicMock()
        mock_client.list.side_effect = ConnectionError("Could not connect to Ollama")
        mock_ollama.Client.return_value = mock_client

        with patch.dict(sys.modules, {"ollama": mock_ollama}):
            result = check_ollama_status()
            self.assertFalse(result)

    def test_check_ollama_status_model_not_installed(self):
        mock_ollama = MagicMock()
        mock_client = MagicMock()
        # Mock models response with a different model installed
        mock_model = MagicMock()
        mock_model.model = "llama2:7b"
        mock_client.list.return_value = MagicMock(models=[mock_model])
        mock_ollama.Client.return_value = mock_client

        with patch.dict(sys.modules, {"ollama": mock_ollama}):
            with patch("modules.llm.MODEL_NAME", "qwen3:1.7b"):
                result = check_ollama_status()
                self.assertFalse(result)

    def test_check_ollama_status_model_installed_successfully(self):
        mock_ollama = MagicMock()
        mock_client = MagicMock()
        mock_model = MagicMock()
        mock_model.model = "qwen3:1.7b:latest"
        mock_client.list.return_value = MagicMock(models=[mock_model])
        mock_ollama.Client.return_value = mock_client

        with patch.dict(sys.modules, {"ollama": mock_ollama}):
            with patch("modules.llm.MODEL_NAME", "qwen3:1.7b"):
                result = check_ollama_status()
                self.assertTrue(result)


class TestLLMFallbackAndRecovery(unittest.TestCase):
    """Tests retry logic, exponential backoff, and error recovery."""

    @patch("modules.llm.time.sleep")
    @patch("modules.llm.GEMINI_API_KEY", "test_valid_key")
    def test_query_gemini_429_retry_success(self, mock_sleep):
        """Simulates 429 rate limit on attempt 1, followed by success on attempt 2."""
        mock_genai = MagicMock()
        mock_client = MagicMock()

        # First call raises 429, second call succeeds
        mock_success_response = MagicMock()
        mock_success_response.text = "Success on retry"
        mock_client.models.generate_content.side_effect = [
            Exception("429 RESOURCE_EXHAUSTED: Quota exceeded"),
            mock_success_response,
        ]
        mock_genai.Client.return_value = mock_client

        with patch.dict(sys.modules, {"google.genai": mock_genai}):
            result = query_gemini("Prompt that gets rate-limited briefly")

        self.assertEqual(result, "Success on retry")
        mock_sleep.assert_called_once_with(2)  # initial retry delay is 2 seconds
        self.assertEqual(mock_client.models.generate_content.call_count, 2)

    @patch("modules.llm.time.sleep")
    @patch("modules.llm.GEMINI_API_KEY", "test_valid_key")
    def test_query_gemini_429_exhausted_retries(self, mock_sleep):
        """Simulates persistent 429 error failing across all 3 retry attempts."""
        mock_genai = MagicMock()
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED")
        mock_genai.Client.return_value = mock_client

        with patch.dict(sys.modules, {"google.genai": mock_genai}):
            result = query_gemini("Prompt that fails repeatedly")

        self.assertEqual(result, "")
        # Should have slept twice (attempt 1 -> sleep 2, attempt 2 -> sleep 4)
        self.assertEqual(mock_sleep.call_count, 2)
        self.assertEqual(mock_client.models.generate_content.call_count, 3)

    @patch("modules.llm.GEMINI_API_KEY", "test_valid_key")
    def test_query_gemini_non_429_fatal_error(self):
        """Non-429 error (such as 400 Bad Request) should fail immediately without retrying."""
        mock_genai = MagicMock()
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("400 INVALID_ARGUMENT: Bad parameter")
        mock_genai.Client.return_value = mock_client

        with patch.dict(sys.modules, {"google.genai": mock_genai}):
            result = query_gemini("Invalid query")

        self.assertEqual(result, "")
        # Must only call once - no retries for bad argument errors
        self.assertEqual(mock_client.models.generate_content.call_count, 1)

    @patch("modules.llm.check_ollama_status", return_value=True)
    def test_query_ollama_strips_thinking_tags(self, mock_status):
        mock_ollama = MagicMock()
        mock_client = MagicMock()
        mock_client.generate.return_value = {
            "response": "<think>Deliberating answer...</think>Clean response text."
        }
        mock_ollama.Client.return_value = mock_client

        with patch.dict(sys.modules, {"ollama": mock_ollama}):
            result = query_ollama("Test prompt")

        self.assertEqual(result, "Clean response text.")

    @patch("modules.llm.query_gemini", return_value="Gemini response")
    @patch("modules.llm.query_ollama", return_value="Ollama response")
    def test_query_llm_provider_routing(self, mock_ollama, mock_gemini):
        # Route to Gemini
        with patch("modules.llm.LLM_PROVIDER", "gemini"):
            res_gemini = query_llm("Hello")
            self.assertEqual(res_gemini, "Gemini response")
            mock_gemini.assert_called_once()
            mock_ollama.assert_not_called()

        mock_gemini.reset_mock()
        mock_ollama.reset_mock()

        # Route to Ollama (local)
        with patch("modules.llm.LLM_PROVIDER", "local"):
            res_local = query_llm("Hello")
            self.assertEqual(res_local, "Ollama response")
            mock_ollama.assert_called_once()
            mock_gemini.assert_not_called()


if __name__ == "__main__":
    unittest.main()
