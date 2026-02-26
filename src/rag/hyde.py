"""
HyDE (Hypothetical Document Embeddings) and HyPE (Hypothetical Prompt Embeddings).

HyDE: For vague queries, generate a hypothetical ideal answer with the LLM, embed it, search.
HyPE: At ingestion, generate hypothetical user questions per chunk and store their embeddings.
"""
from __future__ import annotations

from typing import Any


def _get_llm():
    """Lazy import to avoid requiring OpenAI when RAG not used."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model="gpt-4o-mini", temperature=0.3)


def generate_hypothetical_document(query: str) -> str:
    """
    Generate 1–2 sentences that might appear in an ideal travel suggestion answering the query.
    Used as the search query for HyDE (embed this instead of the vague user query).
    """
    llm = _get_llm()
    prompt = """You are a travel guide. Given the following short or vague travel request, write exactly 1-2 sentences that might appear in an ideal suggestion that would answer it. Be specific: mention activities, places, or types of stay (e.g. yoga, Ganges, boutique hotel). Write as descriptive text, not a question.

Request: {query}

Hypothetical suggestion text:"""
    result = llm.invoke(prompt.format(query=query.strip()))
    text = result.content.strip() if hasattr(result, "content") else str(result).strip()
    return text or query


def generate_hypothetical_questions(doc_content: str, doc_metadata: dict[str, Any], n: int = 2) -> list[str]:
    """
    Generate n hypothetical user questions that this document would answer.
    Used at ingestion (HyPE): store these so queries that match them retrieve this doc.
    """
    name = doc_metadata.get("name", "this place")
    llm = _get_llm()
    prompt = """You are helping index travel content. For the following travel suggestion, write exactly {n} short questions that a traveller might type to find it. One sentence each, natural language. Return only the questions, one per line, no numbering.

Suggestion:
{content}
(Name: {name})

Questions:"""
    result = llm.invoke(
        prompt.format(n=n, content=doc_content[:500], name=name)
    )
    raw = result.content.strip() if hasattr(result, "content") else str(result).strip()
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()][:n]
    return lines
