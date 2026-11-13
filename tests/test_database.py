from app.database import normalize_database_url


def test_normalize_postgres_urls_for_psycopg():
    assert normalize_database_url("postgres://user:pass@host/db") == (
        "postgresql+psycopg://user:pass@host/db"
    )
    assert normalize_database_url("postgresql://user:pass@host/db?sslmode=require") == (
        "postgresql+psycopg://user:pass@host/db?sslmode=require"
    )


def test_leave_sqlite_url_unchanged():
    sqlite_url = "sqlite:///local.db"

    assert normalize_database_url(sqlite_url) == sqlite_url
