# Swapping to AsyncPostgresSaver

Graph code never references `MemorySaver` or `PostgresSaver` directly. It uses `get_checkpointer()` from `src.persistence`.

To migrate to Postgres:

1. Install: `pip install langgraph-checkpoint-postgres "psycopg[binary,pool]"`
2. In `src.persistence`, replace the in-memory checkpointer in `get_checkpointer()` with:

   ```python
   from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # or postgres import PostgresSaver for sync
   DB_URI = os.getenv("DATABASE_URL", "postgresql://...")
   # Use context manager or module-level init; then return the checkpointer.
   ```
3. Call `await checkpointer.setup()` (or `checkpointer.setup()`) once on first use.
4. No changes needed in graph nodes or `StateGraph` compilation: still `compile(checkpointer=get_checkpointer())`.
