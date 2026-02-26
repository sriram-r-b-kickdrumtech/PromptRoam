# Redis cache setup (Phase 9)

PromptRoam uses a **dedicated Redis instance** for caching API responses (RapidAPI, weather, etc.) to reduce cost and latency. This instance runs on a **different port** so it does not affect any existing Redis cluster you already have.

## Start the new Redis instance

From the project root:

```bash
redis-server --port 6380
```

Or with a config file (e.g. `redis-promptroam.conf`):

```conf
port 6380
bind 127.0.0.1
```

Then:

```bash
redis-server redis-promptroam.conf
```

## Environment variables

In `.env` (optional; defaults work if Redis runs on localhost:6380):

| Variable      | Default     | Description                          |
|---------------|-------------|--------------------------------------|
| `REDIS_HOST`  | `localhost` | Redis host for the cache instance    |
| `REDIS_PORT`  | `6380`      | Port (must differ from existing cluster) |
| `REDIS_URL`   | (derived)   | Full URL, e.g. `redis://localhost:6380/0` |

If `REDIS_URL` is set, it overrides `REDIS_HOST` and `REDIS_PORT`.

## Behavior

- **Cache hit:** API response is served from Redis; no external API call.
- **Cache miss:** Request goes to the API; response is stored in Redis with TTL (default 1 hour).
- **Redis down or not configured:** Cache is skipped; all requests go to the API (no crash).

No changes are made to your existing Redis cluster; this setup uses a separate process and port (6380 by default).
