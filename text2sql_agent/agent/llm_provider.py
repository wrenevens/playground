"""
LLM utility functions for prompting.
Abstracts away the specific LLM being used.
Supports: OpenAI, Groq, and other providers.
"""

import logging
import os
import time
import uuid
from typing import Any, Optional, Dict, Tuple
from abc import ABC, abstractmethod

from .llm_metrics import LLMCallMetrics, calculate_cost

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

    @abstractmethod
    def call_with_metrics(
        self,
        system_prompt: str,
        user_message: str,
        stage: str = "unknown"
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Call the LLM and return both response and usage metrics.

        Args:
            system_prompt: System instructions for the LLM
            user_message: The actual query/prompt
            stage: Stage name for logging (e.g., "schema_search", "generate_sql")

        Returns:
            Tuple of (response_text, metrics_dict)
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
            logger.error(
                "OpenAI client not available. Install: pip install openai")
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

    def call_with_metrics(
        self,
        system_prompt: str,
        user_message: str,
        stage: str = "unknown"
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """Call OpenAI API and capture metrics."""
        if not self.client:
            self.initialize()

        call_id = str(uuid.uuid4())
        start_time = time.time()
        response_text = None
        metrics = {}

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            )
            response_text = response.choices[0].message.content

            # Extract token usage
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            # Calculate cost
            input_cost, output_cost, total_cost = calculate_cost(
                self.model, prompt_tokens, completion_tokens
            )

            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            # Create metrics object
            call_metrics = LLMCallMetrics(
                call_id=call_id,
                stage=stage,
                model=self.model,
                provider="openai",
                start_time=start_time,
                end_time=end_time,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                prompt_length=len(system_prompt + user_message),
                response_length=len(response_text) if response_text else 0,
                prompt_text=(system_prompt + user_message),
                response_text=response_text if response_text else None,
                input_cost=input_cost,
                output_cost=output_cost,
                total_cost=total_cost,
                temperature=self.temperature,
                success=True,
                latency_ms=latency_ms,
            )

            metrics = call_metrics.to_dict()

        except Exception as e:
            end_time = time.time()
            logger.error(f"OpenAI call failed: {e}")

            call_metrics = LLMCallMetrics(
                call_id=call_id,
                stage=stage,
                model=self.model,
                provider="openai",
                start_time=start_time,
                end_time=end_time,
                success=False,
                error=str(e),
                temperature=self.temperature,
                latency_ms=(end_time - start_time) * 1000,
            )
            metrics = call_metrics.to_dict()

        return response_text, metrics


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
            logger.error(
                "Groq client not available. Install: pip install groq")
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

    def call_with_metrics(
        self,
        system_prompt: str,
        user_message: str,
        stage: str = "unknown"
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """Call Groq API and capture metrics."""
        if not self.client:
            self.initialize()

        call_id = str(uuid.uuid4())
        start_time = time.time()
        response_text = None
        metrics = {}

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            )
            response_text = response.choices[0].message.content

            # Extract token usage
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            # Calculate cost
            input_cost, output_cost, total_cost = calculate_cost(
                self.model, prompt_tokens, completion_tokens
            )

            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            # Create metrics object
            call_metrics = LLMCallMetrics(
                call_id=call_id,
                stage=stage,
                model=self.model,
                provider="groq",
                start_time=start_time,
                end_time=end_time,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                prompt_length=len(system_prompt + user_message),
                response_length=len(response_text) if response_text else 0,
                prompt_text=(system_prompt + user_message),
                response_text=response_text if response_text else None,
                input_cost=input_cost,
                output_cost=output_cost,
                total_cost=total_cost,
                temperature=self.temperature,
                success=True,
                latency_ms=latency_ms,
            )

            metrics = call_metrics.to_dict()

        except Exception as e:
            error_text = str(e)
            end_time = time.time()

            if "decommission" in error_text.lower() or "model_decommissioned" in error_text.lower():
                logger.error(
                    "Configured Groq model appears deprecated. Set GROQ_MODEL or pass --llm-model. "
                    f"Current fallback default: {DEFAULT_GROQ_MODEL}"
                )

            logger.error(f"Groq call failed: {error_text}")

            call_metrics = LLMCallMetrics(
                call_id=call_id,
                stage=stage,
                model=self.model,
                provider="groq",
                start_time=start_time,
                end_time=end_time,
                success=False,
                error=error_text,
                temperature=self.temperature,
                latency_ms=(end_time - start_time) * 1000,
            )
            metrics = call_metrics.to_dict()

        return response_text, metrics


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


def call_llm_with_metrics(
    system_prompt: str,
    user_message: str,
    provider: str = "openai",
    model: Optional[str] = None,
    stage: str = "unknown"
) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Convenience function to call the LLM with metrics tracking.

    Args:
        system_prompt: System instructions
        user_message: User query
        provider: "openai" or "groq"
        model: Specific model (uses default if None)
        stage: Stage name for logging (e.g., "schema_search", "generate_sql")

    Returns:
        Tuple of (response, metrics_dict) where metrics_dict contains:
        - call_id: Unique identifier
        - stage: Stage name
        - model: Model name
        - provider: Provider name
        - prompt_tokens: Input tokens
        - completion_tokens: Output tokens
        - total_tokens: Total tokens
        - latency_ms: Response time in milliseconds
        - total_cost: Cost in USD
        - success: Whether the call succeeded
        - error: Error message (if any)
        - And many more detailed metrics...

    Example:
        response, metrics = call_llm_with_metrics(
            system, user, provider="groq", stage="schema_search"
        )
        print(f"Tokens: {metrics['total_tokens']}, Cost: ${metrics['total_cost']}")
    """
    llm = get_llm(provider=provider, model=model)
    return llm.call_with_metrics(system_prompt, user_message, stage)
