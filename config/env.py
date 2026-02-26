"""
Startup env validation: fail fast with clear errors if required vars are missing.
"""
import os
from pathlib import Path


def load_dotenv_if_present() -> None:
    """Load .env from project root if python-dotenv is available and .env exists."""
    try:
        from dotenv import load_dotenv
        root = Path(__file__).resolve().parent.parent
        load_dotenv(root / ".env")
    except ImportError:
        pass


# Required for early phases (graph + LLM)
REQUIRED_EARLY = ["OPENAI_API_KEY"]

# Optional; required from Phase 9 (document here for clarity)
OPTIONAL_APIS = [
    "AMADEUS_API_KEY",
    "AMADEUS_API_SECRET",
    "EXPEDIA_RAPID_API_KEY",
    "KIWI_TEQUILA_API_KEY",
    "OPENWEATHERMAP_API_KEY",
    "TOMORROW_IO_API_KEY",
    "FIRECRAWL_API_KEY",
    "RAPIDAPI_API_KEY",
]

# Redis cache: REDIS_URL or REDIS_HOST+REDIS_PORT (default port 6380, separate from existing cluster)
REDIS_PORT_DEFAULT = 6380


def validate_env(*, require_early: bool = True) -> None:
    """
    Validate required env vars. Call at app/CLI startup.
    If require_early is True, missing OPENAI_API_KEY (or other REQUIRED_EARLY) raises.
    """
    load_dotenv_if_present()
    if not require_early:
        return
    missing = [k for k in REQUIRED_EARLY if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            f"Copy .env.example to .env and set values."
        )


def get_optional_env(key: str, default: str = "") -> str:
    """Return env value or default. Does not load .env; call validate_env first if needed."""
    return os.getenv(key, default)
