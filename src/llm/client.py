"""Multi-provider LLM client with streaming support."""

import json
import logging
from typing import Any, Generator, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

# Provider default configurations
PROVIDER_CONFIGS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-v4-flash", "deepseek-chat", "deepseek-reasoner"],
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1-mini"],
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "models": [],  # dynamic
    },
}


def _extract_json_object(text: str) -> Optional[str]:
    """Extract a JSON object with balanced braces from text.

    Unlike a greedy regex, this correctly handles nested objects and
    strings containing braces.

    Args:
        text: Raw text that may contain a JSON object.

    Returns:
        The JSON object string, or None if not found.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    return None


class LLMClient:
    """Unified LLM client supporting multiple OpenAI-compatible providers.

    Usage:
        client = LLMClient(provider="deepseek", model="deepseek-v4-flash", api_key="...")
        response = client.chat([{"role": "user", "content": "Hello"}])
    """

    def __init__(
        self,
        provider: str = "deepseek",
        model: str = "deepseek-v4-flash",
        api_key: str = "",
        base_url: Optional[str] = None,
        thinking: bool = False,
    ):
        """Initialize the LLM client.

        Args:
            provider: Provider name (deepseek, openai, groq, ollama, custom).
            model: Model name.
            api_key: API key for the provider.
            base_url: Override the default base URL.
            thinking: Enable deep thinking/reasoning mode (DeepSeek only).
        """
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.thinking = thinking

        # Determine base URL
        if base_url:
            self.base_url = base_url
        elif provider in PROVIDER_CONFIGS:
            self.base_url = PROVIDER_CONFIGS[provider]["base_url"]
        else:
            self.base_url = ""

        # Initialize OpenAI client
        self._client = OpenAI(
            api_key=api_key or "placeholder",  # will be validated on call
            base_url=self.base_url or None,  # type: ignore[arg-type]
        )

    def validate(self) -> tuple[bool, str]:
        """Validate the client configuration.

        Returns:
            Tuple of (is_valid, message).
        """
        if not self.api_key:
            return False, "API Key 未配置"
        if not self.base_url and self.provider == "custom":
            return False, "自定义 API Base URL 未配置"
        return True, "OK"

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 8192,
        stream: bool = False,
    ) -> str:
        """Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Sampling temperature (0-2). Default 0.3 for code generation.
            max_tokens: Maximum tokens in the response.
            stream: If True, returns the full response after streaming.

        Returns:
            The model's text response.

        Raises:
            ValueError: If the client is misconfigured.
            RuntimeError: If the API call fails.
        """
        valid, msg = self.validate()
        if not valid:
            raise ValueError(msg)

        try:
            extra_body = {}
            if self.thinking and self.provider == "deepseek":
                extra_body["thinking"] = {"type": "enabled"}

            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                timeout=120,
                extra_body=extra_body if extra_body else None,
            )

            if stream:
                content_parts = []
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content_parts.append(chunk.choices[0].delta.content)
                return "".join(content_parts)
            else:
                return response.choices[0].message.content or ""

        except Exception as e:
            error_msg = str(e)
            logger.error("LLM API error: %s", error_msg)
            raise RuntimeError(f"LLM API 调用失败: {error_msg}") from e

    def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 8192,
    ) -> Generator[str, None, None]:
        """Stream chat completion tokens.

        Args:
            messages: List of message dicts.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens.

        Yields:
            Text chunks as they arrive from the API.

        Raises:
            ValueError: If the client is misconfigured.
            RuntimeError: If the API call fails.
        """
        valid, msg = self.validate()
        if not valid:
            raise ValueError(msg)

        try:
            extra_body = {}
            if self.thinking and self.provider == "deepseek":
                extra_body["thinking"] = {"type": "enabled"}

            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                timeout=120,
                extra_body=extra_body if extra_body else None,
            )

            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            error_msg = str(e)
            logger.error("LLM streaming error: %s", error_msg)
            raise RuntimeError(f"LLM API 调用失败: {error_msg}") from e

    def chat_structured(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 16384,
    ) -> dict[str, Any]:
        """Send a chat request and parse the response as JSON.

        Used for getting structured output (chart code, etc.) from the LLM.

        Args:
            messages: List of message dicts.
            temperature: Lower temperature for more deterministic output.
            max_tokens: Maximum tokens.

        Returns:
            Parsed JSON dict.

        Raises:
            ValueError: If the response is not valid JSON.
        """
        response_text = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )

        # Try to extract JSON from the response
        try:
            # First, try direct JSON parse
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code blocks
        import re

        # Match ```json ... ``` or ``` ... ```
        json_pattern = r"```(?:json)?\s*([\s\S]*?)```"
        matches = re.findall(json_pattern, response_text)
        if matches:
            for match in matches:
                try:
                    return json.loads(match.strip())
                except json.JSONDecodeError:
                    continue

        # Match JSON object with balanced braces (handles nested objects)
        json_obj = _extract_json_object(response_text)
        if json_obj:
            try:
                return json.loads(json_obj)
            except json.JSONDecodeError:
                pass

        raise ValueError(
            f"无法解析 LLM 响应为 JSON。响应长度: {len(response_text)} 字符\n"
            f"原始响应:\n{response_text[:800]}"
        )


def create_client_from_config(config: dict) -> LLMClient:
    """Create an LLMClient from a configuration dict.

    Args:
        config: dict with provider, model, api_key, base_url keys.

    Returns:
        Configured LLMClient instance.
    """
    return LLMClient(
        provider=config.get("provider", "deepseek"),
        model=config.get("model", "deepseek-v4-flash"),
        api_key=config.get("api_key", ""),
        base_url=config.get("base_url") or None,
        thinking=config.get("thinking", False),
    )
