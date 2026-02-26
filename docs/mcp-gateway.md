# MCP-only gateway and caching

The app **never calls RapidAPI (or any external API) directly**. All external calls go through **MCP tools** and are **cached in Redis** when possible.

## Flow

```
Executor node (e.g. transport) 
  → call_mcp_tool_cached("search_flights", { origin, destination, date })
      → Redis: cache key = hash(tool_name, arguments)
      → Cache HIT: return cached result (no MCP call)
      → Cache MISS: call MCP server (SSE or stdio) → cache result → return
```

So: **LLM / graph decides to use a tool → our code intercepts → check Redis for (tool + args) → on miss, forward to MCP client → MCP server (e.g. RapidAPI MCP) → cache and return.**

## Configuration

### RapidAPI MCP (recommended)

Use the official RapidAPI MCP server so the app gets live data. The **x-api-host** is **variable per category** (flights, hotels, activities) and **not hardcoded**: you list up to 3 API hosts per category; if one returns an error, the next in the same category is tried automatically.

1. Ensure **Node.js** and **npx** are installed (so `npx mcp-remote` can run).
2. In `.env` set your RapidAPI key and use the placeholder `{{HOST}}` in `MCP_ARGS`:
   ```bash
   RAPIDAPI_API_KEY=your-key-here
   MCP_COMMAND=npx
   MCP_ARGS=["mcp-remote", "https://mcp.rapidapi.com", "--header", "x-api-host: {{HOST}}", "--header", "x-api-key: ${RAPIDAPI_API_KEY}"]
   ```
3. Set **per-category API hosts** (comma-separated, up to 3 per category). The app tries them in order; on error or failure it tries the next in that category:
   ```bash
   MCP_FLIGHTS_HOSTS=flights-sky.p.rapidapi.com,other-flights.p.rapidapi.com,third-flights.p.rapidapi.com
   MCP_HOTELS_HOSTS=booking-com.p.rapidapi.com,hotels-com.p.rapidapi.com
   MCP_ACTIVITIES_HOSTS=tripadvisor-data.p.rapidapi.com,get-your-guide.p.rapidapi.com
   ```
   Subscribe to the APIs you list on [RapidAPI](https://rapidapi.com) and use each API’s host as in the examples above.
4. The gateway expands `${RAPIDAPI_API_KEY}` in `MCP_ARGS` at runtime so the key is not stored in config. At call time it substitutes `{{HOST}}` with the current host for that category.

**Get all variables and key:** RapidAPI MCP supports many APIs (e.g. **Aerodatabox** for flights). The x-api-host value is the *variable*; x-api-key is your key. Run `python scripts/generate_mcp_servers_json.py` to output a full `mcpServers` JSON with variable and key filled from `.env` (use `--template` for placeholders only).

**Single-host (no fallback):** If you do not set `MCP_*_HOSTS`, you can still use a single fixed host by putting it directly in `MCP_ARGS` (no `{{HOST}}`). Then the app uses one connection and no fallback.

Tool names exposed by RapidAPI MCP depend on the API; if they differ from `search_flights` / `search_hotels` / `search_activities`, set `MCP_TOOL_FLIGHTS` etc. in `.env` or adjust in `src/graph/nodes.py`.

### Other MCP servers

- **SSE:** `MCP_SERVER_URL=https://your-mcp-host/sse`
- **Stdio (generic):** `MCP_COMMAND=npx`, `MCP_ARGS=["-y","@your/mcp-server"]`

**Redis:** Same as [Redis setup](redis-setup.md) (e.g. `REDIS_PORT=6380`). If Redis is down, MCP is still called; only caching is skipped.

**MCP cache toggle:** Set `MCP_CACHE_ENABLED=0` to disable Redis caching for MCP (e.g. while verifying the server). Default is off until you confirm MCP works. Set `MCP_CACHE_ENABLED=1` in `.env` after running `scripts/test_mcp_and_cache.py` successfully. With cache enabled, repeated identical tool calls are served from Redis and do not hit the MCP server.

## Tool names

Executor nodes call these tool names with the given argument shapes. Your MCP server must expose tools that match (or you change the names in `src/graph/nodes.py`):

| Node         | Tool name          | Example arguments                          |
|-------------|--------------------|--------------------------------------------|
| Transport   | `search_flights`   | `origin`, `destination`, `date`            |
| Accommodation | `search_hotels`  | `location`, optional `max_budget`          |
| Experience  | `search_activities`| `location`, `interests`                    |

If the MCP server uses different names (e.g. `rapidapi_flight_search`), either configure your MCP to alias them or change the tool names in the node helpers.

## No direct API calls

- `src/rapidapi_client.py` is **not** used by the graph. It remains in the repo for scripts, for reference, or for use inside your own MCP server that talks to RapidAPI.
- All live data for the app comes from `src/mcp_gateway.call_mcp_tool_cached(...)`.
