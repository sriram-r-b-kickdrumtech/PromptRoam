"""
LLM utilities for graph nodes. All nodes use this to call OpenAI.

Every call logs the prompt and response so you can see exactly what went in/out.
"""
from __future__ import annotations

import json
import os
from typing import Any

from config.logging_config import get_logger

log = get_logger(__name__)


def _get_llm():
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.3,
        api_key=os.environ.get("OPENAI_API_KEY"),
    )


def call_llm(system_prompt: str, user_prompt: str, node_name: str) -> str:
    """Call OpenAI with system+user prompt. Logs prompt and response. Returns response text."""
    log.info("[LLM_CALL] node=%s", node_name)
    log.info("[LLM_PROMPT] node=%s system_prompt:\n%s", node_name, system_prompt[:2000])
    log.info("[LLM_PROMPT] node=%s user_prompt:\n%s", node_name, user_prompt[:3000])
    llm = _get_llm()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    response = llm.invoke(messages)
    text = response.content if hasattr(response, "content") else str(response)
    log.info("[LLM_RESPONSE] node=%s response:\n%s", node_name, text[:3000])
    return text


def call_llm_json(system_prompt: str, user_prompt: str, node_name: str) -> dict[str, Any]:
    """Call LLM expecting JSON output. Parses and returns dict; falls back to raw text on parse error."""
    text = call_llm(system_prompt, user_prompt, node_name)
    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        log.warning("[LLM_JSON] node=%s failed to parse JSON, returning raw", node_name)
        return {"raw_response": text}
