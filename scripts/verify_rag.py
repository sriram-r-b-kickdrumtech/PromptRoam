"""
Verify RAG: run after ingest_sample.py. Requires OPENAI_API_KEY and data/chroma populated.

  python scripts/verify_rag.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.rag.store import get_store
from src.rag.retrieval import retrieve_for_agent


def main() -> None:
    store = get_store()
    # Use higher threshold so "cheap hotel" etc. return results
    threshold = 1.5

    queries = [
        "spiritual yoga by the river",
        "cheap hotel in Rishikesh",
        "adventure trek",
    ]
    print("RAG verification (score_threshold=1.5)\n")
    for q in queries:
        items = retrieve_for_agent(store, q, k=3, score_threshold=threshold)
        print(f"  \"{q}\" -> {len(items)} result(s)")
        for x in items[:2]:
            name = x["metadata"].get("name", "?")
            typ = x["metadata"].get("type", "?")
            score = round(x["score"], 3)
            print(f"    - {name} ({typ}) score={score}")
        if not items:
            print("    (none passed threshold)")
        print()
    print("Done. To test in the app: streamlit run app/main.py, then ask for a trip to Rishikesh.")


if __name__ == "__main__":
    main()
