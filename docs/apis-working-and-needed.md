# APIs: What’s Working vs What We Need

This doc lists which APIs **return real data** today and which we **need** (or need correct docs for). Use it to activate similar APIs on RapidAPI and share links so we can wire correct endpoints.

---

## What’s in place per category

| Category   | APIs in registry | Returns real data today | Notes |
|-----------|------------------|--------------------------|--------|
| **Flights**  | aerodatabox, multi-site-flight-search, flight-price-comparison | ✅ aerodatabox only | 1 of 3 returns flights; other two need correct endpoints. |
| **Hotels**   | hotel-api6, expedia13, booking-search | ❌ none | All called; all return 404 or no list. Need working hotel search API + path. |
| **Activities** | tripadvisor-scraper, tripadvisor-data | ❌ none | Both called; no usable list. Need working activities API + path. |
| **Weather**  | openweathermap | ✅ yes | Current weather by city; uses `OPENWEATHERMAP_API_KEY`. |

Everything is wired: each category has a tool (`search_flights`, `search_hotels`, `search_activities`, `get_weather`), the MCP server calls every API in the registry for that tool, and the graph uses the merged result. Missing piece is **working endpoints** for hotels and activities (and optional extra flight APIs).

---

## How to see each API’s results

From repo root (with `RAPIDAPI_API_KEY` and `OPENWEATHERMAP_API_KEY` in `.env`):

```bash
python scripts/call_all_apis_show_results.py
```

This calls all four categories with default params (e.g. Delhi → Goa, 2025-04-15; location Goa for hotels/activities/weather), prints the **full JSON result** for each category, and a **per-API breakdown** (how many items each API returned). So you can see exactly which APIs returned data and what they returned.

---

## 1. Working APIs (we get actual results)

| Category   | API ID        | Name          | Status | Notes |
|-----------|----------------|---------------|--------|--------|
| **Flights** | `aerodatabox` | AeroDataBox   | ✅ Working | Returns real flights by flight number. We use path `/flights/number/{flightNumber}/{dateFrom}/{dateTo}`. [RapidAPI](https://rapidapi.com/aerodatabox/api/aerodatabox) / [Docs](https://doc.aerodatabox.com/rapidapi.html). |
| **Weather** | `openweathermap` | OpenWeatherMap | ✅ Working | Uses `OPENWEATHERMAP_API_KEY`; not RapidAPI. Endpoint `/data/2.5/weather` with `q`, `appid`, `units`. [OpenWeatherMap](https://openweathermap.org/api). |

---

## 2. Registered but not returning data (need correct endpoints or replacement APIs)

### Flights (2 of 3 tried — no data)

| API ID                     | RapidAPI host / name              | What we tried | Issue |
|---------------------------|------------------------------------|---------------|--------|
| `multi-site-flight-search` | multi-site-flight-search.p.rapidapi.com | `GET /search`, `GET /v1/search` with `from`, `to`, `date` (or `origin`, `destination`, `date`) | No 200 / no `flights`/`data`/`results` in response. Need **exact path and query params** from the API’s RapidAPI page. |
| `flight-price-comparison`  | flight-price-comparison.p.rapidapi.com  | Same as above | Same. Need **docs or working example** (path + params). |

**What we need:** Either the **exact endpoint path and query parameters** for these two from their RapidAPI “Code Snippets” / docs, **or** links to **other flight search APIs** you subscribe to (e.g. “Flight Search”, “Skyscanner”, “Amadeus”) so we can add them to the registry and call them.

---

### Hotels (all 3 — no data)

| API ID            | RapidAPI host / name        | What we tried | Issue |
|-------------------|-----------------------------|---------------|--------|
| `hotel-api6`      | hotel-api6.p.rapidapi.com   | `GET /search`, `GET /properties/list`, `GET /v1/hotels/search` with location/city/query/destinationId | All return non-200 or no `hotels`/`properties`/`results`/`data`. Need **exact path and params** from API page. |
| `expedia13`       | expedia13.p.rapidapi.com    | Same path variants | Same. |
| `booking-search`  | booking-search.p.rapidapi.com | Same | Same. |

**What we need:** For **hotel search by city/location** (and optionally dates): either **exact endpoint + query params** for one of the above from their RapidAPI “Code Snippets”, **or** links to **other hotel/booking APIs** you’ve activated (e.g. “Booking.com”, “Hotels”, “Expedia”, “Hotel API”) so we can add them and use the correct paths.

---

### Activities (both — no data)

| API ID                 | RapidAPI host / name              | What we tried | Issue |
|------------------------|------------------------------------|---------------|--------|
| `tripadvisor-scraper`  | tripadvisor-scraper.p.rapidapi.com | `GET /search?query=...`, `GET /location-details?location_id=...` | No 200 or no usable list. Need **exact path and params**. |
| `tripadvisor-data`     | tripadvisor-data.p.rapidapi.com    | `GET /location-details?location_id=113992` | RapidAPI returns **404 — endpoint does not exist** on this host. Need a **different TripAdvisor (or “things to do”) API** with a real search/list endpoint. |

**What we need:** For **activities / things to do by location**: either **exact endpoint** for a TripAdvisor or “attractions” API that has **search by city/location** (or location_id), **or** links to **similar APIs** you’ve activated so we can add them and call the right paths.

---

## 3. Summary: what to give us

So we can get **real results from all three categories**:

1. **Flights**  
   - We already have **AeroDataBox** working.  
   - For the other two: either **exact path + params** for `multi-site-flight-search` and `flight-price-comparison`, or **links to 1–2 other flight search APIs** you’ve subscribed to.

2. **Hotels**  
   - **Exact path + query params** for **one** of: hotel-api6, expedia13, booking-search (from their RapidAPI “Code Snippets”), **or** links to **1–2 hotel/booking APIs** you’ve activated.

3. **Activities**  
   - **Exact path + params** for an API that does **search/list activities by location**, **or** links to **1–2 “things to do” / TripAdvisor / attractions APIs** you’ve activated.

When you have links (and optionally copy-paste of the “Code Snippets” request URL and params), we can add them to `config/api_registry.json` and update `scripts/mcp_server_promptroam.py` so every category returns real data through MCP.

---

## 4. Current stance: existing APIs only; plug in more later

We use only the **existing working APIs** for now (AeroDataBox for flights, OpenWeatherMap for weather). Hotels and activities may return empty; the graph injects a single fallback item so the flow does not break. To **plug in** more APIs later:

1. Add the API to `config/api_registry.json` (in `apis` and in `tool_to_apis` for the right tool).
2. If the API has known endpoints, add them under that API’s `endpoints` in the registry.
3. In `scripts/mcp_server_promptroam.py`, add any API-specific request logic (path/params) in `_collect_flights_from_api`, `_tool_search_hotels`, or `_tool_search_activities` as needed.
4. No change to the graph or MCP gateway: they already call every API listed in `tool_to_apis` and merge results.

---

## 5. Where this is used in code

- **API list and mapping:** `config/api_registry.json` (`apis`, `tool_to_apis`).
- **Actual HTTP calls (all 3 per category):** `scripts/mcp_server_promptroam.py` (and in-process fallback in `src/graph/nodes.py`).
- **RapidAPI key:** `RAPIDAPI_API_KEY` in `.env`.
- **Weather:** `OPENWEATHERMAP_API_KEY` in `.env`; OpenWeatherMap is not on RapidAPI.
