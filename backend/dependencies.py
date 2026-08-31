"""
dependencies.py – LLM client initialization.
Reads LLM_PROVIDER from the environment and returns the appropriate client.
Supports: "gemini" (Google), "openai", "anthropic", "groq"
"""

import os
from dotenv import load_dotenv
from functools import lru_cache

load_dotenv()


def get_settings() -> dict:
    """Return resolved configuration from environment variables."""
    load_dotenv(override=True)
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    return {
        "provider": provider,
        # Gemini
        "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        # OpenAI
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        # Anthropic
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "anthropic_model": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620"),
        # Groq
        "groq_api_key": os.getenv("GROQ_API_KEY", ""),
        "groq_model": os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b"),
        # General
        "max_transcript_tokens": int(os.getenv("MAX_TRANSCRIPT_TOKENS", "1800")),
        "cors_origin": os.getenv("CORS_ORIGIN", "http://localhost:5173"),
    }


def get_llm_client():
    """Return the configured LLM client based on LLM_PROVIDER env var."""
    settings = get_settings()
    provider = settings["provider"]

    if provider == "gemini":
        if not settings["gemini_api_key"]:
            raise EnvironmentError(
                "GEMINI_API_KEY is not set. "
                "Get a free key at https://aistudio.google.com/app/apikey"
            )
        from google import genai
        return genai.Client(api_key=settings["gemini_api_key"])

    elif provider == "anthropic":
        if not settings["anthropic_api_key"]:
            raise EnvironmentError("ANTHROPIC_API_KEY is not set.")
        from anthropic import AsyncAnthropic
        return AsyncAnthropic(api_key=settings["anthropic_api_key"])

    elif provider == "groq":
        if not settings["groq_api_key"]:
            raise EnvironmentError("GROQ_API_KEY is not set.")
        from groq import AsyncGroq
        return AsyncGroq(api_key=settings["groq_api_key"])

    else:  # openai
        if not settings["openai_api_key"]:
            raise EnvironmentError("OPENAI_API_KEY is not set.")
        from openai import AsyncOpenAI
        return AsyncOpenAI(api_key=settings["openai_api_key"])
