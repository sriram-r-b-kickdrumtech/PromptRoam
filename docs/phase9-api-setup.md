# Phase 9: External APIs — Setup Guide

PromptRoam uses **RapidAPI** for travel (flights, accommodation, routing) and **OpenWeatherMap** for weather. **Do not commit real keys**; use `.env` and keep `.env` in `.gitignore`.

**MCP-only:** The app calls **only MCP tools** (never direct RapidAPI). See [MCP gateway and caching](mcp-gateway.md).

**Redis cache:** MCP tool responses are cached in a **separate Redis instance** (default port **6380**). See [Redis setup](redis-setup.md).

---

## 1. APIs we use

| Category        | Source              | Purpose                          | Env variable              |
|----------------|---------------------|----------------------------------|---------------------------|
| **LLM**        | OpenAI              | Graph, RAG, HyDE/HyPE            | `OPENAI_API_KEY`          |
| **Weather**    | OpenWeatherMap      | Forecasts, rescheduling          | `OPENWEATHERMAP_API_KEY`  |
| **Travel**     | RapidAPI (all-in-one) | Flights, hotels, routing, etc. | `RAPIDAPI_API_KEY`        |

Travel APIs (flights, accommodation, routing) are accessed **via RapidAPI**: one API key, multiple subscribed APIs. You can also use a **RapidAPI MCP** if you have it configured.

**Optional env:** `RAPIDAPI_APP_NAME` — your application name (e.g. `default-application_11603250`) for reference; not required for API calls.

---

## 2. OpenWeatherMap (free)

- **Purpose:** Weather forecasts for activity rescheduling.
- **Sign up:** https://home.openweathermap.org/users/sign_up → confirm email → key in email or at https://home.openweathermap.org/api_keys.
- **Env:** `OPENWEATHERMAP_API_KEY`
- **Base URL:** `https://api.openweathermap.org`
- **Docs:** https://openweathermap.org/api

---

## 3. RapidAPI (travel: flights, hotels, routing)

We use **one RapidAPI key** for all travel-related APIs. You subscribe to the APIs you need on RapidAPI; each has its own host and endpoints.

### 3.1 Get your key

1. Go to **https://rapidapi.com/** and sign in (or create an account).
2. **My Account** → **API Keys** (or [rapidapi.com/developer/dashboard](https://rapidapi.com/developer/dashboard)).
3. Create or copy your **API Key**.
4. In `.env` set:  
   `RAPIDAPI_API_KEY=<your-key>`

### 3.2 Subscribe to APIs

In RapidAPI, search and subscribe to the APIs you want to use, for example:

- **Flights** — e.g. “Flight Search”, “Skyscanner”, “Amadeus”, or any flight API you’ve subscribed to.
- **Hotels / accommodation** — e.g. “Booking”, “Hotels”, “Expedia”, or any hotel API.
- **Routing / multi-city** — if needed for complex itineraries.

Each API has a **host** (e.g. `booking-com.p.rapidapi.com`) and **endpoints** shown on its RapidAPI page. The same `RAPIDAPI_API_KEY` is sent as `X-RapidAPI-Key`; the host is sent as `X-RapidAPI-Host` (per API).

**LangGraph:** The app does **not** call RapidAPI directly. Nodes call MCP tools via `src/mcp_gateway.py`; your MCP server (e.g. RapidAPI MCP) holds the API key. `.mcp_secrets` is a key-free host registry for reference or for use inside your MCP server.

### 3.3 Calling RapidAPI from code

Typical request headers:

- `X-RapidAPI-Key`: value of `RAPIDAPI_API_KEY`
- `X-RapidAPI-Host`: host for that specific API (from its RapidAPI page)

Base URL is usually `https://<host>` (e.g. `https://booking-com.p.rapidapi.com`).

### 3.4 List your subscribed APIs

- **Script (try first):** From repo root with `.env` loaded:
  ```bash
  python scripts/list_rapidapi_subscriptions.py
  ```
  This calls RapidAPI’s GraphQL Platform API. If that API is only for Enterprise Hub, the script will point you to the dashboard.

- **Dashboard:** [RapidAPI Developer Dashboard](https://rapidapi.com/developer/dashboard) → **Subscriptions & Usage** to see all APIs you’re subscribed to, with names and usage.

### 3.5 RapidAPI MCP

If you use an **MCP server for RapidAPI** (e.g. [RapidAPI MCP on Pipedream](https://mcp.pipedream.com/app/rapidapi) or [SecurFi RapidAPI MCP](https://www.pulsemcp.com/servers/securfi-rapidapi)):

1. Configure the MCP in Cursor (e.g. **Settings → MCP** or your Cursor MCP config file) with your `RAPIDAPI_API_KEY`.
2. Once connected, use the MCP’s tools from Cursor to list or call your subscribed APIs.

PromptRoam can then call travel APIs via MCP tools instead of (or in addition to) direct HTTP.

---

## 4. Environment file template

Copy into `.env` (never commit real values):

```bash
# LLM (required)
OPENAI_API_KEY=

# Weather (free)
OPENWEATHERMAP_API_KEY=

# Travel via RapidAPI (one key for all subscribed travel APIs)
RAPIDAPI_API_KEY=

# Optional: application name for reference
# RAPIDAPI_APP_NAME=default-application_11603250
```

---

## 5. Validation and fail-fast

At startup (e.g. in `config/env.py`), validate:

- **Required:** `OPENAI_API_KEY`, `OPENWEATHERMAP_API_KEY`, `RAPIDAPI_API_KEY` (or allow running with stubs if `RAPIDAPI_API_KEY` is missing and show a clear message).
- On missing/invalid key: fail fast with a clear message and point to this doc.

---

## 6. Verifiable inventory rule

Every itinerary item must have at least one of:

- `booking_url`
- `external_id`
- `price_quote` (with source and timestamp)

No hallucinated inventory; all suggestions must be verifiable via RapidAPI (or other configured sources) and weather via OpenWeatherMap.

---

## 7. Optional: direct API keys (reference only)

If you ever switch away from RapidAPI to direct provider APIs, you would use separate keys. We do **not** use these by default:

| Provider        | Env variables                          | Notes                    |
|----------------|----------------------------------------|---------------------------|
| Amadeus        | `AMADEUS_API_KEY`, `AMADEUS_API_SECRET` | OAuth; token endpoint     |
| Expedia Rapid  | `EXPEDIA_RAPID_API_KEY`, `_SECRET`     | Different from RapidAPI   |
| Kiwi Tequila   | `KIWI_TEQUILA_API_KEY`                 | tequila.kiwi.com          |
| Firecrawl      | `FIRECRAWL_API_KEY`                    | Scraping; optional        |

Current setup: **RapidAPI + OpenWeatherMap only** (plus OpenAI).
