from psycopg_pool import AsyncConnectionPool

from config.settings import get_settings

SESSION_OPTIONS = (
    "-c default_transaction_read_only=on "
    "-c statement_timeout=5s "
    "-c idle_in_transaction_session_timeout=30s "
    "-c search_path=rag,ops,public"
)
MIN_SIZE = 1
MAX_SIZE = 5
ACQUIRE_TIMEOUT_S = 5.0


def build_pool() -> AsyncConnectionPool | None:
    """Read-only, time-limited sessions; None when PG_DSN is not set."""
    dsn = get_settings().pg_dsn
    if dsn is None:
        return None

    return AsyncConnectionPool(
        conninfo=dsn.get_secret_value(),
        kwargs={"options": SESSION_OPTIONS, "autocommit": True},
        min_size=MIN_SIZE,
        max_size=MAX_SIZE,
        timeout=ACQUIRE_TIMEOUT_S,
        open=False,
        name="crocol",
    )
