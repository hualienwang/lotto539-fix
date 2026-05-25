import sqlite3
from http.server import ThreadingHTTPServer
import threading
from urllib.request import urlopen

import pytest

from app import (
    BadRequestError,
    build_backtest_response,
    build_summary,
    create_handler,
    run_crawl,
)


def create_history_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE history (
                "期別" TEXT PRIMARY KEY,
                "開獎日" TEXT NOT NULL,
                "大小順序" TEXT NOT NULL,
                "頭獎中獎注數" INTEGER NOT NULL
            )
            """
        )
        conn.executemany(
            'INSERT INTO history ("期別", "開獎日", "大小順序", "頭獎中獎注數") VALUES (?, ?, ?, ?)',
            [
                ("115000001", "115/01/01", "01 02 03 04 05", 0),
                ("115000002", "115/01/02", "01 02 06 07 08", 1),
                ("115000003", "115/01/03", "09 10 11 12 13", 2),
            ],
        )


def test_build_summary_returns_database_status_recent_draws_and_frequency(tmp_path):
    db_path = tmp_path / "lotto-539.db"
    create_history_db(db_path)

    summary = build_summary(db_path)

    assert summary["database"] == str(db_path)
    assert summary["total_draws"] == 3
    assert summary["latest_draw"] == {
        "issue": "115000003",
        "draw_date": "2026-01-03",
        "numbers": [9, 10, 11, 12, 13],
        "jackpot_winners": 2,
    }
    assert summary["recent_draws"][0]["issue"] == "115000003"
    assert summary["frequency"][:3] == [
        {"number": 1, "count": 2},
        {"number": 2, "count": 2},
        {"number": 3, "count": 1},
    ]


def test_build_backtest_response_runs_frequency_strategy(tmp_path):
    db_path = tmp_path / "lotto-539.db"
    create_history_db(db_path)

    response = build_backtest_response(
        db_path,
        {
            "strategy": "frequency",
            "test_from": "2026-01-03",
            "train_before": "2026-01-03",
            "recent_window": 20,
            "seed": None,
            "ticket_cost": 50,
        },
    )

    assert response["strategy"] == "frequency"
    assert response["total_draws"] == 1
    assert response["hit_distribution"] == {
        "0": 1,
        "1": 0,
        "2": 0,
        "3": 0,
        "4": 0,
        "5": 0,
    }
    assert response["predictions"][0]["issue"] == "115000003"
    assert response["predictions"][0]["predicted_numbers"] == [1, 2, 3, 4, 5]


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"strategy": "not-real"}, "Invalid strategy"),
        ({"strategy": "frequency", "test_from": "bad-date"}, "Invalid date"),
        ({"strategy": "frequency", "recent_window": 0}, "recent_window"),
        ({"strategy": "frequency", "ticket_cost": 0}, "ticket_cost"),
    ],
)
def test_build_backtest_response_rejects_invalid_payloads(tmp_path, payload, message):
    db_path = tmp_path / "lotto-539.db"
    create_history_db(db_path)

    with pytest.raises(BadRequestError, match=message):
        build_backtest_response(db_path, payload)


def test_run_crawl_uses_injected_fetcher_and_saves_records(tmp_path):
    db_path = tmp_path / "lotto-539.db"

    def fake_fetcher():
        return [
            {
                "期別": "115000004",
                "開獎日": "115/01/04",
                "大小順序": "14 15 16 17 18",
                "頭獎中獎注數": 0,
            }
        ]

    response = run_crawl(db_path, fetcher=fake_fetcher)

    assert response == {
        "fetched": 1,
        "inserted": 1,
        "latest_issue": "115000004",
        "earliest_issue": "115000004",
    }
    assert build_summary(db_path)["total_draws"] == 1


def test_favicon_request_returns_no_content(tmp_path):
    db_path = tmp_path / "lotto-539.db"
    create_history_db(db_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(db_path))
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        response = urlopen(f"http://127.0.0.1:{server.server_port}/favicon.ico")
        assert response.status == 204
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
