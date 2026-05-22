"""
core/ai_provider.py
The ONLY module in the codebase that makes direct LLM API calls.
No phase, route, or integration should import an AI SDK directly.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class ProviderName(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI    = "openai"
    GOOGLE    = "google"
    GROQ      = "groq"


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def __post_init__(self):
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens


@dataclass
class AIResponse:
    content: str
    provider: str
    model: str
    usage: TokenUsage
    latency_ms: float
    raw: Any = field(default=None, repr=False)


class AIProviderError(Exception):
    def __init__(self, message: str, provider: str, model: str, original: Optional[Exception] = None):
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.original = original


class AIRateLimitError(AIProviderError):
    pass


class AIAuthError(AIProviderError):
    pass


class AIContextLengthError(AIProviderError):
    pass


class AIProvider:
    def __init__(
        self,
        provider_name: str,
        model: str,
        api_key: str,
        max_retries: int = 3,
        timeout: int = 60,
    ) -> None:
        try:
            self.provider = ProviderName(provider_name)
        except ValueError:
            raise AIProviderError(
                f"Unknown provider '{provider_name}'.",
                provider=provider_name,
                model=model,
            )
        self.model = model
        self._api_key = api_key
        self.max_retries = max_retries
        self.timeout = timeout

    async def complete(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> AIResponse:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(AIRateLimitError),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            reraise=True,
        ):
            with attempt:
                return await self._dispatch(
                    user_message=user_message,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

    async def _dispatch(self, **kwargs: Any) -> AIResponse:
        start = time.monotonic()

        if self.provider == ProviderName.ANTHROPIC:
            response = await self._call_anthropic(**kwargs)
        elif self.provider == ProviderName.OPENAI:
            response = await self._call_openai(**kwargs)
        elif self.provider == ProviderName.GOOGLE:
            response = await self._call_google(**kwargs)
        elif self.provider == ProviderName.GROQ:
            response = await self._call_groq(**kwargs)
        else:
            raise AIProviderError(f"No handler for provider '{self.provider}'", self.provider.value, self.model)

        response.latency_ms = (time.monotonic() - start) * 1000
        return response

    async def _call_anthropic(self, user_message, system_prompt, temperature, max_tokens, **kwargs):
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        params = dict(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": user_message}],
        )
        if system_prompt:
            params["system"] = system_prompt
        try:
            raw = await client.messages.create(**params)
            content = raw.content[0].text if raw.content else ""
            usage = TokenUsage(input_tokens=raw.usage.input_tokens, output_tokens=raw.usage.output_tokens)
            return AIResponse(content=content, provider="anthropic", model=self.model, usage=usage, latency_ms=0, raw=raw)
        except anthropic.RateLimitError as exc:
            raise AIRateLimitError("Anthropic rate limit hit.", "anthropic", self.model, exc) from exc
        except anthropic.AuthenticationError as exc:
            raise AIAuthError("Anthropic API key invalid.", "anthropic", self.model, exc) from exc
        except Exception as exc:
            raise AIProviderError(str(exc), "anthropic", self.model, exc) from exc

    async def _call_openai(self, user_message, system_prompt, temperature, max_tokens, **kwargs):
        import openai
        client = openai.AsyncOpenAI(api_key=self._api_key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        try:
            raw = await client.chat.completions.create(
                model=self.model, messages=messages,
                temperature=temperature, max_tokens=max_tokens,
            )
            content = raw.choices[0].message.content or ""
            usage = TokenUsage(
                input_tokens=raw.usage.prompt_tokens if raw.usage else 0,
                output_tokens=raw.usage.completion_tokens if raw.usage else 0,
            )
            return AIResponse(content=content, provider="openai", model=self.model, usage=usage, latency_ms=0, raw=raw)
        except openai.RateLimitError as exc:
            raise AIRateLimitError("OpenAI rate limit hit.", "openai", self.model, exc) from exc
        except openai.AuthenticationError as exc:
            raise AIAuthError("OpenAI API key invalid.", "openai", self.model, exc) from exc
        except Exception as exc:
            raise AIProviderError(str(exc), "openai", self.model, exc) from exc

    async def _call_google(self, user_message, system_prompt, temperature, max_tokens, **kwargs):
        import google.generativeai as genai
        genai.configure(api_key=self._api_key)
        config = genai.types.GenerationConfig(temperature=temperature, max_output_tokens=max_tokens)
        model_instance = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt or "",
            generation_config=config,
        )
        try:
            raw = await model_instance.generate_content_async(user_message)
            content = raw.text or ""
            input_tokens = raw.usage_metadata.prompt_token_count if raw.usage_metadata else 0
            output_tokens = raw.usage_metadata.candidates_token_count if raw.usage_metadata else 0
            return AIResponse(content=content, provider="google", model=self.model, usage=TokenUsage(input_tokens, output_tokens), latency_ms=0, raw=raw)
        except Exception as exc:
            raise AIProviderError(str(exc), "google", self.model, exc) from exc

    async def _call_groq(self, user_message, system_prompt, temperature, max_tokens, **kwargs):
        from groq import AsyncGroq
        client = AsyncGroq(api_key=self._api_key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        try:
            raw = await client.chat.completions.create(
                model=self.model, messages=messages,
                temperature=temperature, max_tokens=max_tokens,
            )
            content = raw.choices[0].message.content or ""
            usage = TokenUsage(
                input_tokens=raw.usage.prompt_tokens if raw.usage else 0,
                output_tokens=raw.usage.completion_tokens if raw.usage else 0,
            )
            return AIResponse(content=content, provider="groq", model=self.model, usage=usage, latency_ms=0, raw=raw)
        except Exception as exc:
            raise AIProviderError(str(exc), "groq", self.model, exc) from exc


def build_provider_from_config(provider_name: str, model: str, encrypted_api_key: str) -> AIProvider:
    from core.config import get_encryption_manager
    api_key = get_encryption_manager().decrypt(encrypted_api_key)
    return AIProvider(provider_name=provider_name, model=model, api_key=api_key)