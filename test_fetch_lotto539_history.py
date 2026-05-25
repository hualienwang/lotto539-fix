from datetime import date
import sqlite3

from fetch_lotto539_history import build_default_url, save_history


def test_build_default_url_uses_current_month_and_previous_two_months():
    url = build_default_url(date(2026, 5, 25))

    assert "start_month=2026-03" in url
    assert "end_month=2026-05" in url


def test_build_default_url_handles_year_boundary():
    url = build_default_url(date(2026, 1, 7))

    assert "start_month=2025-11" in url
    assert "end_month=2026-01" in url


def test_save_history_only_inserts_missing_records(tmp_path):
    db_path = tmp_path / "lotto-539.db"
    existing_record = {
        "期別": "115000126",
        "開獎日": "115/05/23",
        "大小順序": "06 15 16 24 38",
        "頭獎中獎注數": 1,
    }
    new_record = {
        "期別": "115000127",
        "開獎日": "115/05/25",
        "大小順序": "01 02 03 04 05",
        "頭獎中獎注數": 0,
    }

    first_inserted = save_history(db_path, [existing_record])
    second_inserted = save_history(
        db_path,
        [
            {**existing_record, "頭獎中獎注數": 99},
            new_record,
        ],
    )

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            'SELECT "期別", "頭獎中獎注數" FROM history ORDER BY "期別"'
        ).fetchall()

    assert first_inserted == 1
    assert second_inserted == 1
    assert rows == [("115000126", 1), ("115000127", 0)]
