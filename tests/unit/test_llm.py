"""
Unit tests for src/agents/llm.py

Tests LLM initialization, model selection, parameter validation,
and convenience functions for different model types.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.agents.llm import (
    COMPLEX_MODEL,
    DEFAULT_MODEL,
    FAST_MODEL,
    HAIKU_MODEL,
    OPUS_MODEL,
    SONNET_MODEL,
    get_haiku_llm,
    get_llm,
    get_opus_llm,
    get_sonnet_llm,
)


class TestModelConstants:
    """Test that model constants are correctly defined."""

    def test_model_constants_defined(self):
        """Model constants should have expected values."""
        assert SONNET_MODEL == "claude-sonnet-4-20250514"
        assert HAIKU_MODEL == "claude-3-haiku-20240307"
        assert OPUS_MODEL == "claude-opus-4-5-20251101"

    def test_model_selection_aliases(self):
        """Model selection aliases should point to correct models."""
        assert DEFAULT_MODEL == SONNET_MODEL
        assert FAST_MODEL == HAIKU_MODEL
        assert COMPLEX_MODEL == OPUS_MODEL


class TestGetLLM:
    """Test get_llm() function with various parameters."""

    @patch("src.agents.llm.ChatAnthropic")
    @patch("src.agents.llm.get_settings")
    def test_get_llm_default_parameters(self, mock_get_settings, mock_chat_anthropic):
        """get_llm() should use default parameters when none provided."""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.get_llm_api_key.return_value = "sk-ant-test-key"
        mock_get_settings.return_value = mock_settings

        # Mock ChatAnthropic
        mock_llm_instance = MagicMock()
        mock_chat_anthropic.return_value = mock_llm_instance

        # Call get_llm with defaults
        result = get_llm()

        # Verify settings was called
        mock_get_settings.assert_called_once()
        mock_settings.get_llm_api_key.assert_called_once()

        # Verify ChatAnthropic was initialized with correct defaults
        mock_chat_anthropic.assert_called_once_with(
            model=DEFAULT_MODEL,
            anthropic_api_key="sk-ant-test-key",
            temperature=0.7,
            max_tokens=4096,
            streaming=False,
        )

        # Verify return value
        assert result == mock_llm_instance

    @patch("src.agents.llm.ChatAnthropic")
    @patch("src.agents.llm.get_settings")
    def test_get_llm_custom_model(self, mock_get_settings, mock_chat_anthropic):
        """get_llm() should use custom model when provided."""
        mock_settings = MagicMock()
        mock_settings.get_llm_api_key.return_value = "sk-ant-test-key"
        mock_get_settings.return_value = mock_settings

        get_llm(model=HAIKU_MODEL)

        mock_chat_anthropic.assert_called_once_with(
            model=HAIKU_MODEL,
            anthropic_api_key="sk-ant-test-key",
            temperature=0.7,
            max_tokens=4096,
            streaming=False,
        )

    @patch("src.agents.llm.ChatAnthropic")
    @patch("src.agents.llm.get_settings")
    def test_get_llm_custom_temperature(self, mock_get_settings, mock_chat_anthropic):
        """get_llm() should use custom temperature when provided."""
        mock_settings = MagicMock()
        mock_settings.get_llm_api_key.return_value = "sk-ant-test-key"
        mock_get_settings.return_value = mock_settings

        get_llm(temperature=0.1)

        mock_chat_anthropic.assert_called_once_with(
            model=DEFAULT_MODEL,
            anthropic_api_key="sk-ant-test-key",
            temperature=0.1,
            max_tokens=4096,
            streaming=False,
        )

    @patch("src.agents.llm.ChatAnthropic")
    @patch("src.agents.llm.get_settings")
    def test_get_llm_custom_max_tokens(self, mock_get_settings, mock_chat_anthropic):
        """get_llm() should use custom max_tokens when provided."""
        mock_settings = MagicMock()
        mock_settings.get_llm_api_key.return_value = "sk-ant-test-key"
        mock_get_settings.return_value = mock_settings

        get_llm(max_tokens=2048)

        mock_chat_anthropic.assert_called_once_with(
            model=DEFAULT_MODEL,
            anthropic_api_key="sk-ant-test-key",
            temperature=0.7,
            max_tokens=2048,
            streaming=False,
        )

    @patch("src.agents.llm.ChatAnthropic")
    @patch("src.agents.llm.get_settings")
    def test_get_llm_streaming_enabled(self, mock_get_settings, mock_chat_anthropic):
        """get_llm() should enable streaming when requested."""
        mock_settings = MagicMock()
        mock_settings.get_llm_api_key.return_value = "sk-ant-test-key"
        mock_get_settings.return_value = mock_settings

        get_llm(streaming=True)

        mock_chat_anthropic.assert_called_once_with(
            model=DEFAULT_MODEL,
            anthropic_api_key="sk-ant-test-key",
            temperature=0.7,
            max_tokens=4096,
            streaming=True,
        )

    @patch("src.agents.llm.ChatAnthropic")
    @patch("src.agents.llm.get_settings")
    def test_get_llm_all_custom_parameters(self, mock_get_settings, mock_chat_anthropic):
        """get_llm() should accept all custom parameters together."""
        mock_settings = MagicMock()
        mock_settings.get_llm_api_key.return_value = "sk-ant-test-key"
        mock_get_settings.return_value = mock_settings

        get_llm(
            model=OPUS_MODEL,
            temperature=0.3,
            max_tokens=8192,
            streaming=True
        )

        mock_chat_anthropic.assert_called_once_with(
            model=OPUS_MODEL,
            anthropic_api_key="sk-ant-test-key",
            temperature=0.3,
            max_tokens=8192,
            streaming=True,
        )

    @patch("src.agents.llm.get_settings")
    def test_get_llm_missing_api_key(self, mock_get_settings):
        """get_llm() should raise ValueError when API key is not configured."""
        mock_settings = MagicMock()
        mock_settings.get_llm_api_key.side_effect = ValueError(
            "ANTHROPIC_API_KEY not configured. Please set it in your .env file."
        )
        mock_get_settings.return_value = mock_settings

        with pytest.raises(ValueError) as exc_info:
            get_llm()

        assert "ANTHROPIC_API_KEY not configured" in str(exc_info.value)


class TestGetSonnetLLM:
    """Test get_sonnet_llm() convenience function."""

    @patch("src.agents.llm.ChatAnthropic")
    @patch("src.agents.llm.get_settings")
    def test_get_sonnet_llm_default(self, mock_get_settings, mock_chat_anthropic):
        """get_sonnet_llm() should use SONNET_MODEL."""
        mock_settings = MagicMock()
        mock_settings.get_llm_api_key.return_value = "sk-ant-test-key"
        mock_get_settings.return_value = mock_settings

        mock_llm = MagicMock()
        mock_chat_anthropic.return_value = mock_llm

        result = get_sonnet_llm()

        mock_chat_anthropic.assert_called_once_with(
            model=SONNET_MODEL,
            anthropic_api_key="sk-ant-test-key",
            temperature=0.7,
            max_tokens=4096,
            streaming=False,
        )
        assert result == mock_llm

    @patch("src.agents.llm.ChatAnthropic")
    @patch("src.agents.llm.get_settings")
    def test_get_sonnet_llm_with_kwargs(self, mock_get_settings, mock_chat_anthropic):
        """get_sonnet_llm() should pass through kwargs to get_llm()."""
        mock_settings = MagicMock()
        mock_settings.get_llm_api_key.return_value = "sk-ant-test-key"
        mock_get_settings.return_value = mock_settings

        get_sonnet_llm(temperature=0.5, max_tokens=2048)

        mock_chat_anthropic.assert_called_once_with(
            model=SONNET_MODEL,
            anthropic_api_key="sk-ant-test-key",
            temperature=0.5,
            max_tokens=2048,
            streaming=False,
        )


class TestGetHaikuLLM:
    """Test get_haiku_llm() convenience function."""

    @patch("src.agents.llm.ChatAnthropic")
    @patch("src.agents.llm.get_settings")
    def test_get_haiku_llm_default(self, mock_get_settings, mock_chat_anthropic):
        """get_haiku_llm() should use HAIKU_MODEL."""
        mock_settings = MagicMock()
        mock_settings.get_llm_api_key.return_value = "sk-ant-test-key"
        mock_get_settings.return_value = mock_settings

        mock_llm = MagicMock()
        mock_chat_anthropic.return_value = mock_llm

        result = get_haiku_llm()

        mock_chat_anthropic.assert_called_once_with(
            model=HAIKU_MODEL,
            anthropic_api_key="sk-ant-test-key",
            temperature=0.7,
            max_tokens=4096,
            streaming=False,
        )
        assert result == mock_llm

    @patch("src.agents.llm.ChatAnthropic")
    @patch("src.agents.llm.get_settings")
    def test_get_haiku_llm_with_kwargs(self, mock_get_settings, mock_chat_anthropic):
        """get_haiku_llm() should pass through kwargs to get_llm()."""
        mock_settings = MagicMock()
        mock_settings.get_llm_api_key.return_value = "sk-ant-test-key"
        mock_get_settings.return_value = mock_settings

        get_haiku_llm(temperature=0.9, streaming=True)

        mock_chat_anthropic.assert_called_once_with(
            model=HAIKU_MODEL,
            anthropic_api_key="sk-ant-test-key",
            temperature=0.9,
            max_tokens=4096,
            streaming=True,
        )


class TestGetOpusLLM:
    """Test get_opus_llm() convenience function."""

    @patch("src.agents.llm.ChatAnthropic")
    @patch("src.agents.llm.get_settings")
    def test_get_opus_llm_default(self, mock_get_settings, mock_chat_anthropic):
        """get_opus_llm() should use OPUS_MODEL."""
        mock_settings = MagicMock()
        mock_settings.get_llm_api_key.return_value = "sk-ant-test-key"
        mock_get_settings.return_value = mock_settings

        mock_llm = MagicMock()
        mock_chat_anthropic.return_value = mock_llm

        result = get_opus_llm()

        mock_chat_anthropic.assert_called_once_with(
            model=OPUS_MODEL,
            anthropic_api_key="sk-ant-test-key",
            temperature=0.7,
            max_tokens=4096,
            streaming=False,
        )
        assert result == mock_llm

    @patch("src.agents.llm.ChatAnthropic")
    @patch("src.agents.llm.get_settings")
    def test_get_opus_llm_with_kwargs(self, mock_get_settings, mock_chat_anthropic):
        """get_opus_llm() should pass through kwargs to get_llm()."""
        mock_settings = MagicMock()
        mock_settings.get_llm_api_key.return_value = "sk-ant-test-key"
        mock_get_settings.return_value = mock_settings

        get_opus_llm(temperature=0.3, max_tokens=8192)

        mock_chat_anthropic.assert_called_once_with(
            model=OPUS_MODEL,
            anthropic_api_key="sk-ant-test-key",
            temperature=0.3,
            max_tokens=8192,
            streaming=False,
        )


class TestLLMIntegration:
    """Integration tests for LLM initialization scenarios."""

    @patch("src.agents.llm.ChatAnthropic")
    @patch("src.agents.llm.get_settings")
    def test_all_model_types_use_same_api_key(
        self, mock_get_settings, mock_chat_anthropic
    ):
        """All model convenience functions should use the same API key source."""
        mock_settings = MagicMock()
        mock_settings.get_llm_api_key.return_value = "sk-ant-test-key"
        mock_get_settings.return_value = mock_settings

        # Call all convenience functions
        get_sonnet_llm()
        get_haiku_llm()
        get_opus_llm()

        # Should have called get_settings 3 times (once per function)
        assert mock_get_settings.call_count == 3

        # Each should have retrieved the API key
        assert mock_settings.get_llm_api_key.call_count == 3

        # All should have used the same API key
        for call in mock_chat_anthropic.call_args_list:
            assert call.kwargs["anthropic_api_key"] == "sk-ant-test-key"

    @patch("src.agents.llm.ChatAnthropic")
    @patch("src.agents.llm.get_settings")
    def test_different_models_for_different_use_cases(
        self, mock_get_settings, mock_chat_anthropic
    ):
        """Different convenience functions should use appropriate models."""
        mock_settings = MagicMock()
        mock_settings.get_llm_api_key.return_value = "sk-ant-test-key"
        mock_get_settings.return_value = mock_settings

        # Simulate different use cases
        fast_llm = get_haiku_llm()  # Fast queries
        standard_llm = get_sonnet_llm()  # Standard operations
        complex_llm = get_opus_llm()  # Complex reasoning

        # Verify different models were requested
        calls = mock_chat_anthropic.call_args_list
        assert calls[0].kwargs["model"] == HAIKU_MODEL
        assert calls[1].kwargs["model"] == SONNET_MODEL
        assert calls[2].kwargs["model"] == OPUS_MODEL

    @patch("src.agents.llm.ChatAnthropic")
    @patch("src.agents.llm.get_settings")
    def test_temperature_variations_for_different_needs(
        self, mock_get_settings, mock_chat_anthropic
    ):
        """Temperature can be tuned for different agent needs."""
        mock_settings = MagicMock()
        mock_settings.get_llm_api_key.return_value = "sk-ant-test-key"
        mock_get_settings.return_value = mock_settings

        # Different temperature for different scenarios
        deterministic = get_llm(temperature=0.1)  # Structured output
        balanced = get_llm(temperature=0.7)  # Default
        creative = get_llm(temperature=0.9)  # More varied responses

        calls = mock_chat_anthropic.call_args_list
        assert calls[0].kwargs["temperature"] == 0.1
        assert calls[1].kwargs["temperature"] == 0.7
        assert calls[2].kwargs["temperature"] == 0.9
