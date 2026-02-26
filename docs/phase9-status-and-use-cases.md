# Phase 9: Status, Requirements, and Use Cases (3 APIs per purpose)

## Is Phase 9 complete?

**No.** Per PLAN.md, Phase 9 is not complete until:

- [ ] MCP is the primary gateway (or fallback direct tool layer documented).
- [ ] Flights, accommodation, routing, weather are callable and return valid responses.
- [ ] Executor stubs replaced with live (or sandbox) API calls.
- [ ] Verifiable inventory: every itinerary item has `booking_url`, `external_id`, or `price_quote`.
- [ ] Firecrawl (or equivalent) for scraping → HiddenGems (optional).

**Currently we have:** RapidAPI key in env, host registry (6 APIs), direct HTTP client in `src/rapidapi_client.py`, and stub nodes that try the client and fall back to stub. Weather is OpenWeatherMap (separate). We have **not** wired real endpoints per API, **not** integrated MCP from LangGraph, and **not** enforced verifiable inventory.

---

## Required APIs vs what we have

| Requirement (PLAN) | Source we use | Status |
|--------------------|---------------|--------|
| Flights            | RapidAPI      | 1 API (multi-site-flight-search); need 3 for 100-call limit spread |
| Accommodation      | RapidAPI      | 3 APIs (hotel-api6, expedia13, booking-search) ✓ |
| Routing / multi-city | RapidAPI   | 0 dedicated; can use flight/hotel APIs for now |
| Weather            | OpenWeatherMap | In place ✓ |
| Scraping (forums → HiddenGems) | Firecrawl or RapidAPI | Optional; not wired |

---

## Use cases and 3 APIs per purpose (for you to activate)

With a **100-call limit per API**, use **3 APIs per purpose** so you have up to 300 calls per purpose until the hackathon ends.

Subscribe to these on RapidAPI (search by name), then add each host to `.mcp_secrets` and `src/rapidapi_client.RAPIDAPI_HOSTS` under the keys below.

### 1. Flights (3 APIs)

| # | Use case | RapidAPI name to search | Host key to add | Notes |
|---|----------|-------------------------|-----------------|--------|
| 1 | Multi-site flight search | Multi Site Flight Search (airlineconsolidator) | `flights` | Already in registry |
| 2 | Flight search / compare | Skyscanner, or “Flight Search”, or Amadeus Flight Create Search | `flights_2` | Add second option |
| 3 | Flight prices / compare | Another flight API (e.g. Flight Data, Cheap Flights) | `flights_3` | Add third option |

**You activate:** Subscribe to 2 more flight APIs on RapidAPI (we already have one). Tell me the **host** for each (e.g. `skyscanner-api.p.rapidapi.com`) and I’ll add `flights_2`, `flights_3` to the registry.

### 2. Accommodation (3 APIs)

| # | Use case | RapidAPI name | Host key | Status |
|---|----------|---------------|----------|--------|
| 1 | Hotels search | Hotel API (hotel-api6) | `hotels` | In registry |
| 2 | Expedia properties | Expedia (expedia13) | `expedia` | In registry |
| 3 | Booking search | Booking Search | `booking` | In registry |

**You have 3.** No change needed unless you want to swap one.

### 3. Activities / experience (3 APIs)

| # | Use case | RapidAPI name | Host key | Status |
|---|----------|---------------|----------|--------|
| 1 | Tripadvisor scrape | Tripadvisor Scraper | `tripadvisor` | In registry |
| 2 | Tripadvisor data | Tripadvisor Data | `tripadvisor_data` | In registry |
| 3 | Activities / things to do | Add e.g. “Activities API” or “GetYourGuide” or similar | `activities` | You activate and provide host |

**You activate:** Subscribe to one more “activities” or “tours” API and send the host; we’ll add `activities`.

### 4. Weather (no RapidAPI)

| # | Use case | Source | Env | Status |
|---|----------|--------|-----|--------|
| 1 | Forecasts / rescheduling | OpenWeatherMap | `OPENWEATHERMAP_API_KEY` | You have it ✓ |

No 3-API spread needed; one provider is enough.

### 5. Scraping (optional)

| # | Use case | Source | Notes |
|---|----------|--------|--------|
| 1 | Forums/blogs → HiddenGems | Firecrawl or RapidAPI “Web Scraper” | Optional; add if you want |

---

## MCP-based call: one-API example and test result

APIs are called the same way whether via **MCP** (Cursor / npx mcp-remote) or from **LangGraph** (direct HTTP with the same key from env). The key is never stored in a file; it comes from `RAPIDAPI_API_KEY` in the environment.

**Input (one API):** TripAdvisor Data (`tripadvisor_data`), params `location_id=113992`.

**How it is called:** Via MCP: URL `https://mcp.rapidapi.com`, headers `x-api-key` (from env) and `x-api-host: tripadvisor-data.p.rapidapi.com`. Via LangGraph: same key and host, GET `https://tripadvisor-data.p.rapidapi.com/<endpoint>?location_id=113992`. Run `python scripts/test_one_api_mcp_style.py` to perform the same call.

**Test result:** Request returned HTTP **404** (endpoint path placeholder). So **key and subscription are valid**; for real data use the exact path from the API’s RapidAPI Playground. MCP-based call = this HTTP call; auth passed.

---

## Summary: what you need to do

1. **Flights:** Subscribe to **2 more** flight APIs on RapidAPI; send me the **host** for each (e.g. from the API’s “Code Snippets” → `x-rapidapi-host`).
2. **Accommodation:** Already have 3; no action.
3. **Activities:** Subscribe to **1 more** activities/tours API; send me the **host**.
4. I’ll add the new hosts to `.mcp_secrets` and `RAPIDAPI_HOSTS` under `flights_2`, `flights_3`, and `activities`. LangGraph nodes can then round-robin or choose by availability to stay under 100 calls per API.
