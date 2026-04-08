"""
LLM utility functions for prompting.
Abstracts away the specific LLM being used.
Supports: OpenAI, Groq, and other providers.
"""

import logging
import os
from typing import Any, Optional
from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)


try:
    from ..configs.default import (
        DEFAULT_OPENAI_MODEL as CONFIG_DEFAULT_OPENAI_MODEL,
        DEFAULT_GROQ_MODEL as CONFIG_DEFAULT_GROQ_MODEL,
    )
except Exception:
    # Fallbacks if config import is unavailable.
    CONFIG_DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
    CONFIG_DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


DEFAULT_OPENAI_MODEL = CONFIG_DEFAULT_OPENAI_MODEL
DEFAULT_GROQ_MODEL = CONFIG_DEFAULT_GROQ_MODEL


def resolve_model(provider: str, model: Optional[str] = None) -> str:
    """
    Resolve the model name from explicit arg, env var, then provider default.

    Priority:
    1) explicit model argument
    2) OPENAI_MODEL / GROQ_MODEL env var
    3) built-in provider default
    """
    provider = provider.lower()

    if model:
        return model

    if provider == "openai":
        return os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    if provider == "groq":
        return os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)

    raise ValueError(f"Unknown provider: {provider}. Use 'openai' or 'groq'")


class LLMProvider(ABC):
    """
    Abstract base class for LLM calls.
    Implement this to add new providers (OpenAI, Groq, Anthropic, local, etc.)
    """
    
    def __init__(self, model: str, temperature: float = 0.3):
        self.model = model
        self.temperature = temperature
        self.client = None
    
    @abstractmethod
    def initialize(self):
        """Initialize the LLM client."""
        pass
    
    @abstractmethod
    def call(self, system_prompt: str, user_message: str) -> Optional[str]:
        """
        Call the LLM with a system prompt and user message.
        
        Args:
            system_prompt: System instructions for the LLM
            user_message: The actual query/prompt
        
        Returns:
            LLM response text, or None on error
        """
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider (GPT-3.5, GPT-4, etc.)"""
    
    def __init__(self, model: str = DEFAULT_OPENAI_MODEL, temperature: float = 0.3):
        super().__init__(model, temperature)
    
    def initialize(self):
        """Initialize OpenAI client."""
        try:
            from openai import OpenAI
            self.client = OpenAI()
            logger.info(f"Initialized OpenAI client with model: {self.model}")
        except ImportError:
            logger.error("OpenAI client not available. Install: pip install openai")
            raise
    
    def call(self, system_prompt: str, user_message: str) -> Optional[str]:
        """Call OpenAI API."""
        if not self.client:
            self.initialize()
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI call failed: {e}")
            return None


class GroqProvider(LLMProvider):
    """Groq LLM provider (fast inference)"""
    
    def __init__(self, model: str = DEFAULT_GROQ_MODEL, temperature: float = 0.3):
        super().__init__(model, temperature)
    
    def initialize(self):
        """Initialize Groq client."""
        try:
            from groq import Groq
            self.client = Groq()
            logger.info(f"Initialized Groq client with model: {self.model}")
        except ImportError:
            logger.error("Groq client not available. Install: pip install groq")
            raise
    
    def call(self, system_prompt: str, user_message: str) -> Optional[str]:
        """Call Groq API."""
        if not self.client:
            self.initialize()
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            error_text = str(e)
            logger.error(f"Groq call failed: {error_text}")
            if "decommission" in error_text.lower() or "model_decommissioned" in error_text.lower():
                logger.error(
                    "Configured Groq model appears deprecated. Set GROQ_MODEL or pass --llm-model. "
                    f"Current fallback default: {DEFAULT_GROQ_MODEL}"
                )
            return None


# Global LLM instances
_llm_instances = {}


def get_llm(provider: str = "openai", model: Optional[str] = None) -> LLMProvider:
    """
    Get or create a global LLM instance.
    
    Args:
        provider: "openai" or "groq"
        model: Specific model name (uses defaults if None)
    
    Returns:
        LLMProvider instance
    
    Example:
        llm = get_llm("openai", "gpt-4")
        llm = get_llm("groq", DEFAULT_GROQ_MODEL)
    """
    provider = provider.lower()

    model = resolve_model(provider=provider, model=model)
    
    # Use model as key for instance caching
    cache_key = f"{provider}:{model}"
    
    if cache_key not in _llm_instances:
        if provider == "openai":
            _llm_instances[cache_key] = OpenAIProvider(model=model)
        elif provider == "groq":
            _llm_instances[cache_key] = GroqProvider(model=model)
        
        _llm_instances[cache_key].initialize()
    
    return _llm_instances[cache_key]


def call_llm(
    system_prompt: str,
    user_message: str,
    provider: str = "openai",
    model: Optional[str] = None
) -> Optional[str]:
    """
    Convenience function to call the LLM.
    
    Args:
        system_prompt: System instructions
        user_message: User query
        provider: "openai" or "groq"
        model: Specific model (uses default if None)
    
    Returns:
        LLM response or None on error
    
    Example:
        response = call_llm(system, user, provider="groq")
        response = call_llm(system, user, provider="openai", model="gpt-4")
    """
    llm = get_llm(provider=provider, model=model)
    return llm.call(system_prompt, user_message)
