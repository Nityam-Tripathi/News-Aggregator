from datetime import datetime, timezone

from app import scheduler


def test_parse_published_at_converts_to_utc_naive_datetime():
    value = "2026-11-20T10:30:00+05:30"

    parsed = scheduler._parse_published_at(value)

    assert parsed == datetime(2026, 11, 20, 5, 0, 0)
    assert parsed.tzinfo is None


def test_parse_published_at_handles_missing_and_invalid_values():
    assert scheduler._parse_published_at(None) is None
    assert scheduler._parse_published_at("not-a-date") is None


def test_start_scheduler_is_idempotent(monkeypatch):
    calls = []
    fake_scheduler = type(
        "FakeScheduler",
        (),
        {
            "running": True,
            "add_job": lambda *args, **kwargs: calls.append("job"),
            "start": lambda *args, **kwargs: calls.append("start"),
        },
    )()
    monkeypatch.setattr(scheduler, "_scheduler", fake_scheduler)
    monkeypatch.setattr(
        scheduler, "ingest_news", lambda: calls.append("ingest")
    )

    scheduler.start_scheduler()

    assert calls == []
