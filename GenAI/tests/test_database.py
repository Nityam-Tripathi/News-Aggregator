from app.database import _normalize_database_url


def test_normalize_legacy_postgres_url():
    assert _normalize_database_url(
        "postgres://user:pass@localhost:5432/news"
    ) == "postgresql+psycopg2://user:pass@localhost:5432/news"


def test_normalize_postgresql_url():
    assert _normalize_database_url(
        "postgresql://user:pass@localhost:5432/news"
    ) == "postgresql+psycopg2://user:pass@localhost:5432/news"


def test_preserve_explicit_database_driver():
    url = "postgresql+psycopg://user:pass@localhost:5432/news"
    assert _normalize_database_url(url) == url
