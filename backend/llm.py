"""
llm.py – LLM streaming wrapper.

Supports Gemini (Google), OpenAI, Anthropic, and Groq based on LLM_PROVIDER env var.
"""

import re
from typing import AsyncGenerator, List
from dependencies import get_settings

# ─── Language Instructions ────────────────────────────────────────────────────

LANGUAGE_INSTRUCTIONS = {
    "english": "Use clear, formal **English** only throughout the notes.",
    "hindi": "पूरे नोट्स **हिंदी** में लिखें। सभी तकनीकी शब्द जैसे API, LLM आदि अंग्रेजी में रहेंगे लेकिन explanation हिंदी में।",
    "hinglish": "Use a natural blend of **English + Hinglish** (mix of Hindi and English). Technical terms in English, explanations in easy Hinglish. e.g. 'Yeh concept bahut important hai kyunki...'",
}

# ─── Note Generation Prompts ──────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are an expert tech educator and academic note-taker. "
    "Your output MUST be ONLY clean markdown notes for the user. "
    "Do NOT output any thinking, meta-reasoning, planning steps, or <think> tags. "
    "Start directly with the first markdown heading."
)

NOTE_GENERATION_PROMPT = """You are an expert academic note-taker and technical interview coach. Given the transcript of a YouTube lecture or educational video, produce **comprehensive, structured markdown notes** that faithfully follow the lecture's flow.

## Language Instruction
{language_instruction}

## Output Format & Requirements
- Use `##` headings for major topics (following the EXACT order of the lecture).
- Use `###` headings for sub-topics.
- For every key concept/topic:
  - Provide a clear **Definition**.
  - Provide a **Real-world Example** (real-life / production scenario).
  - Include **Interview Focus** (why it's important or asked in interviews).
- Use bullet points (`-`), **bold** terms, and `code blocks` where appropriate.
- End the entire document with a `## Summary` section (2-3 sentences).

## CRITICAL RULES
1. **NO Timestamps**: Do NOT include any timestamps like `[00:01:23]`.
2. **Follow Transcript Order**: Preserve the exact sequential flow of concepts.
3. **NO Meta Text**: Output ONLY the final markdown notes. No thinking, no <think> tags.

## Transcript
{transcript}

---
Now produce the structured notes directly:"""

CONTINUATION_PROMPT = """You are continuing to produce structured markdown notes for a long lecture.
Continue from where the previous section left off. Do NOT repeat content.
Start directly with the next `##` section. No timestamps, no <think> tags.
Language: {language_instruction}

## Next portion of transcript
{transcript}

---
Continue the notes:"""

# ─── Quiz / Flashcard / Summary Prompts ──────────────────────────────────────

QUIZ_PROMPT = """You are a technical interview coach. Analyze the following notes and identify all major topics/sections. For EACH topic, generate 3-4 MCQ questions that test deep understanding of that concept.

Return ONLY valid JSON in this exact format (no markdown, no explanation, no extra text):
{{
  "topics": [
    {{
      "topic": "Topic Name Here",
      "questions": [
        {{
          "question": "Question text?",
          "options": ["A) option1", "B) option2", "C) option3", "D) option4"],
          "correct": "A",
          "explanation": "Why A is correct"
        }}
      ]
    }}
  ]
}}

Notes:
{notes}"""

FLASHCARD_PROMPT = """Based on the following notes, generate exactly 10 study flashcards (question + answer pairs).

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{{
  "flashcards": [
    {{
      "front": "What is X?",
      "back": "X is... (concise answer in 1-2 sentences)"
    }}
  ]
}}

Notes:
{notes}"""

SUMMARY_PROMPT = """Give a concise TL;DR summary of these notes in 4-5 bullet points. Each bullet should capture one key takeaway.
Keep it short and punchy. Use the same language as the notes (English/Hindi/Hinglish).

Return ONLY markdown bullet points, no extra text.

Notes:
{notes}"""

STITCH_SEPARATOR = "\n\n---\n\n"


# ─── Think Tag Filter ─────────────────────────────────────────────────────────

async def _filter_think_tags(token_stream: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
    """
    Strip <think>...</think> reasoning blocks from model output.
    Qwen/DeepSeek always put <think>...</think> at the very START before actual content.
    Strategy: buffer tokens until </think> is found, then stream everything after.
    """
    buffer = ""
    found_think = False
    past_think = False

    async for token in token_stream:
        # Once past all think blocks, stream directly
        if past_think:
            yield token
            continue

        buffer += token

        if not found_think:
            if "<think>" in buffer:
                found_think = True
                # Yield any text that appeared before <think>
                before = buffer.split("<think>", 1)[0]
                if before.strip():
                    yield before
                # Keep only the part after <think>
                buffer = buffer.split("<think>", 1)[1]
            elif len(buffer) > 50:
                # No <think> tag after 50 chars — this model doesn't use think tags
                past_think = True
                yield buffer
                buffer = ""

        if found_think and not past_think:
            if "</think>" in buffer:
                past_think = True
                after = buffer.split("</think>", 1)[1].lstrip("\n\r ")
                if after:
                    yield after
                buffer = ""
            # else: still inside <think>, keep buffering (discard reasoning content)

    # Yield leftover buffer if no think tags were ever found
    if buffer and not past_think:
        yield buffer


# ─── Main entry point ─────────────────────────────────────────────────────────

async def stream_notes(
    chunks: List[str],
    is_chunked: bool = False,
    language: str = "hinglish",
    model: str = None,
) -> AsyncGenerator[str, None]:
    """
    Given a list of transcript chunks, stream markdown note tokens.
    _filter_think_tags is applied PER CHUNK so separators never confuse the filter.
    """
    import asyncio
    settings = get_settings()
    provider = settings["provider"]
    lang_instr = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["hinglish"])

    for i, chunk in enumerate(chunks):
        if i > 0:
            yield STITCH_SEPARATOR
            if provider == "groq":
                await asyncio.sleep(1.5)

        prompt = (
            NOTE_GENERATION_PROMPT.format(transcript=chunk, language_instruction=lang_instr)
            if i == 0
            else CONTINUATION_PROMPT.format(transcript=chunk, language_instruction=lang_instr)
        )

        if provider == "gemini":
            raw = _stream_gemini(prompt, settings)
        elif provider == "anthropic":
            raw = _stream_anthropic(prompt, settings)
        elif provider == "groq":
            raw = _stream_groq(prompt, settings, model=model)
        else:
            raw = _stream_openai(prompt, settings)

        async for token in _filter_think_tags(raw):
            yield token


def strip_think(text: str) -> str:
    """Remove any <think>...</think> reasoning blocks from text."""
    if not text:
        return ""
    # Strip complete <think>...</think>
    clean = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # If <think> was opened but not closed
    clean = re.sub(r"<think>.*", "", clean, flags=re.DOTALL)
    return clean.strip()


async def call_llm(prompt: str, json_mode: bool = False) -> str:
    """Single non-streaming LLM call with retry, fallback, and think-tag removal."""
    settings = get_settings()
    provider = settings["provider"]

    if provider == "groq":
        from groq import AsyncGroq, RateLimitError
        client = AsyncGroq(api_key=settings["groq_api_key"])
        
        # Primary models to try in order of fallback
        models_to_try = [
            settings["groq_model"],
            "qwen/qwen3.6-27b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-120b",
        ]
        seen = set()
        models_to_try = [m for m in models_to_try if not (m in seen or seen.add(m))]
        
        last_error = None
        for model_name in models_to_try:
            try:
                # Include system prompt and /no_think for Qwen reasoning suppression
                messages = [
                    {"role": "system", "content": "You are a direct, concise AI assistant. Do not output internal thoughts, reasoning steps, or <think> tags."},
                    {"role": "user", "content": f"/no_think\n\n{prompt}"},
                ]
                kwargs = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": 0.2,
                    "max_tokens": 3000,
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                
                resp = await client.chat.completions.create(**kwargs)
                content = resp.choices[0].message.content or ""
                cleaned = strip_think(content)
                if cleaned.strip():
                    return cleaned
            except RateLimitError as e:
                last_error = e
                continue
            except Exception as e:
                # If json_object not supported or other error, retry without response_format
                if json_mode:
                    try:
                        resp = await client.chat.completions.create(
                            model=model_name,
                            messages=[
                                {"role": "system", "content": "Output valid JSON only. No thinking tags."},
                                {"role": "user", "content": f"/no_think\n\n{prompt}"},
                            ],
                            temperature=0.2,
                            max_tokens=3000,
                        )
                        content = resp.choices[0].message.content or ""
                        cleaned = strip_think(content)
                        if cleaned.strip():
                            return cleaned
                    except Exception as inner_e:
                        last_error = inner_e
                        continue
                last_error = e
                continue
        
        if last_error:
            raise last_error
        return ""

    elif provider == "openai":
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings["openai_api_key"])
        kwargs = {
            "model": settings["openai_model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 3000,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    elif provider == "gemini":
        import asyncio
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=settings["gemini_api_key"])
        loop = asyncio.get_event_loop()
        config_kwargs = {"temperature": 0.2, "max_output_tokens": 3000}
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"
            
        result = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=settings["gemini_model"],
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )
        )
        return result.text or ""

    return ""


# ─── Provider implementations ─────────────────────────────────────────────────

async def _stream_gemini(prompt: str, settings: dict) -> AsyncGenerator[str, None]:
    """Stream tokens from the Google Gemini API using google-genai SDK."""
    import asyncio
    import threading
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings["gemini_api_key"])
    model = settings["gemini_model"]
    full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _producer():
        try:
            response_stream = client.models.generate_content_stream(
                model=model,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=8192,
                ),
            )
            for chunk in response_stream:
                if chunk.text:
                    loop.call_soon_threadsafe(queue.put_nowait, ("token", chunk.text))
        except Exception as e:
            loop.call_soon_threadsafe(queue.put_nowait, ("error", str(e)))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

    thread = threading.Thread(target=_producer, daemon=True)
    thread.start()

    while True:
        kind, value = await queue.get()
        if kind == "done":
            break
        elif kind == "error":
            raise RuntimeError(f"Gemini API error: {value}")
        else:
            yield value


async def _stream_openai(prompt: str, settings: dict) -> AsyncGenerator[str, None]:
    """Stream tokens from the OpenAI API."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings["openai_api_key"])
    stream = await client.chat.completions.create(
        model=settings["openai_model"],
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        stream=True,
        temperature=0.3,
        max_tokens=8192,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content


async def _stream_anthropic(prompt: str, settings: dict) -> AsyncGenerator[str, None]:
    """Stream tokens from the Anthropic API."""
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings["anthropic_api_key"])
    async with client.messages.stream(
        model=settings["anthropic_model"],
        max_tokens=8192,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}],
        system=SYSTEM_PROMPT,
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def _stream_groq(prompt: str, settings: dict, model: str = None) -> AsyncGenerator[str, None]:
    """Stream tokens from the Groq API with fallback models on rate limits."""
    from groq import AsyncGroq, RateLimitError

    client = AsyncGroq(api_key=settings["groq_api_key"])
    user_message = f"/no_think\n\n{prompt}"
    
    primary_model = model or settings["groq_model"]
    models_to_try = [
        primary_model,
        "qwen/qwen3.6-27b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-120b",
    ]
    
    # Avoid duplicate models in list
    seen = set()
    deduped_models = [m for m in models_to_try if not (m in seen or seen.add(m))]

    last_err = None
    for model_name in deduped_models:
        try:
            stream = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                stream=True,
                temperature=0.3,
                max_tokens=4096,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
            return
        except RateLimitError as e:
            last_err = e
            continue
        except Exception as e:
            last_err = e
            continue

    if last_err:
        raise last_err
