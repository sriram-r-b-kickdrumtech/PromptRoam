# API Registry & Local MCP Server

## Registry: `config/api_registry.json`

Every API used by PromptRoam is listed here with:

- **id**, **name**, **category** (flights | hotels | activities | weather)
- **base_url**, **auth** (rapidapi | query), **docs_url**
- **endpoints**: path, method, params from official docs

APIs registered:

| Category   | APIs |
|-----------|------|
| Flights   | AeroDataBox, Multi Site Flight Search, Flight price comparison |
| Hotels    | Hotel API (hotel-api6), Expedia, Booking Search |
| Activities| Tripadvisor Scraper, Tripadvisor Data |
| Weather   | OpenWeatherMap |

Docs links in the registry point to official API documentation (RapidAPI, OpenWeatherMap, AeroDataBox, etc.).

## Local MCP Server: `scripts/mcp_server_promptroam.py`

Exposes these tools by calling the registered APIs over HTTP:

- **search_flights** (origin, destination, date) → AeroDataBox + others
- **search_hotels** (location, max_budget)
- **search_activities** (location, interests)
- **get_weather** (q or location) → OpenWeatherMap

### Use the local MCP server

In `.env`:

```bash
MCP_COMMAND=python
MCP_ARGS=["scripts/mcp_server_promptroam.py"]
# Leave MCP_FLIGHTS_HOSTS etc. empty so the app uses this single server (no host substitution).
```

Ensure `RAPIDAPI_API_KEY` and (for weather) `OPENWEATHERMAP_API_KEY` are set. The server reads them from the environment.

### Keep using RapidAPI MCP

Leave `MCP_COMMAND=npx` and `MCP_ARGS=[...mcp.rapidapi.com...]` and set `MCP_FLIGHTS_HOSTS` / `.mcp_secrets` as before. The app will use RapidAPI MCP with host substitution.
