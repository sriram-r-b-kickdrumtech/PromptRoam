"""
Real ingestion: seed the Chroma vector store with sample hotels and attractions.

Run from repo root with promptroam env active and OPENAI_API_KEY set:
  python scripts/ingest_sample.py
  python scripts/ingest_sample.py --hype   # also add HyPE (hypothetical questions per doc)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root on path and load .env
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.rag.ingestion import (
    parse_hotel_from_dict,
    parse_attraction_from_dict,
    knowledge_object_to_document,
)
from src.rag.store import get_store, add_knowledge_objects

SAMPLE_HOTELS = [
    {
        "name": "Ganges View Resort",
        "description": "Boutique eco lodge by the Ganges in Rishikesh. Yoga and meditation retreats, spiritual atmosphere, river views. Peaceful stay with organic meals and morning yoga included.",
        "url": "https://example.com/book/ganges-view",
        "price_tier": 75.0,
        "location": "Rishikesh",
        "location_coordinates": (30.0869, 78.2676),
        "amenities": ["wifi", "yoga", "restaurant", "river view"],
        "seasonality": "peak",
        "category": "boutique",
    },
    {
        "name": "Mountain Trail Lodge",
        "description": "Budget-friendly lodge for trekkers and adventure seekers. Base for hiking and outdoor activities. Simple rooms, hearty meals, great for under-100 stays.",
        "url": "https://example.com/book/mountain-trail",
        "price_tier": 45.0,
        "location": "Rishikesh",
        "amenities": ["wifi", "parking"],
        "category": "budget",
    },
    {
        "name": "Luxury Rishikesh Spa",
        "description": "Premium spa hotel with Ayurveda and wellness programs. High-end accommodation, pool, and direct booking with real-time pricing.",
        "url": "https://example.com/book/luxury-spa",
        "price_tier": 200.0,
        "location": "Rishikesh",
        "amenities": ["spa", "pool", "wifi", "restaurant"],
        "category": "resort",
    },
]

SAMPLE_ATTRACTIONS = [
    {
        "name": "Bungee jumping by the Ganges",
        "description": "Spiritual adventure: bungee jumping near the Ganges. Combines thrill with the sacred river setting. Popular with spiritual adventure seekers.",
        "url": "https://example.com/activities/bungee-ganges",
        "location": "Rishikesh",
        "location_coordinates": (30.0869, 78.2676),
        "category": "spiritual",
        "price_tier": 55.0,
    },
    {
        "name": "Morning yoga by the river",
        "description": "Yoga and meditation sessions by the Ganges. Spiritual and peaceful experience for all levels.",
        "url": "https://example.com/activities/yoga-river",
        "location": "Rishikesh",
        "category": "spiritual",
        "price_tier": 25.0,
    },
    {
        "name": "Himalayan trek base camp",
        "description": "Adventure trekking and hiking base. Multi-day treks and outdoor activities for adventure enthusiasts.",
        "url": "https://example.com/activities/trek-base",
        "location": "Rishikesh",
        "category": "adventure",
        "price_tier": 80.0,
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest sample travel Knowledge Objects into Chroma.")
    parser.add_argument("--hype", action="store_true", help="Add HyPE: hypothetical questions per doc (extra LLM calls).")
    args = parser.parse_args()

    store = get_store()
    documents: list[tuple[str, dict]] = []

    for data in SAMPLE_HOTELS:
        obj = parse_hotel_from_dict(data)
        documents.append(knowledge_object_to_document(obj))

    for data in SAMPLE_ATTRACTIONS:
        obj = parse_attraction_from_dict(data)
        documents.append(knowledge_object_to_document(obj))

    add_knowledge_objects(store, documents)
    print(f"Ingested {len(documents)} Knowledge Objects into Chroma (promptroam_travel).")

    if args.hype:
        from src.rag.hyde import generate_hypothetical_questions
        hype_docs: list[tuple[str, dict]] = []
        for text, meta in documents:
            try:
                questions = generate_hypothetical_questions(text, meta, n=2)
                for q in questions:
                    hype_docs.append((q, dict(meta)))
            except Exception as e:
                print(f"HyPE skip {meta.get('name', '?')}: {e}")
        if hype_docs:
            add_knowledge_objects(store, hype_docs)
            print(f"Added {len(hype_docs)} HyPE hypothetical-question entries.")
    print("Persist directory: data/chroma (or CHROMA_PERSIST_DIR).")


if __name__ == "__main__":
    main()
