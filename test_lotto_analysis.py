from datetime import date
import sqlite3

import pytest

from lotto_analysis import (
    Draw,
    count_number_frequency,
    load_draws,
    parse_numbers,
    parse_roc_date,
    summarize_draw,
)


def test_parse_roc_date_converts_taiwan_year_to_gregorian_date():
    assert parse_roc_date("115/05/23") == date(2026, 5, 23)


@pytest.mark.parametrize("value", ["", "2026-05-23", "115/13/01", "abc/05/23"])
def test_parse_roc_date_rejects_invalid_values(value):
    with pytest.raises(ValueError, match=value or "empty"):
        parse_roc_date(value)


def test_parse_numbers_returns_sorted_tuple_of_five_unique_numbers():
    assert parse_numbers("06 15 16 24 38") == (6, 15, 16, 24, 38)


@pytest.mark.parametrize(
    "value",
    ["01 02 03 04", "01 02 03 04 04", "00 02 03 04 05", "01 02 03 04 40"],
)
def test_parse_numbers_rejects_invalid_values(value):
    with pytest.raises(ValueError, match=value):
        parse_numbers(value)


def test_summarize_draw_returns_basic_features():
    draw = Draw(
        issue="115000126",
        draw_date=date(2026, 5, 23),
        numbers=(6, 15, 16, 24, 38),
        jackpot_winners=1,
    )

    assert summarize_draw(draw) == {
        "issue": "115000126",
        "draw_date": date(2026, 5, 23),
        "sum": 99,
        "odd_count": 1,
        "even_count": 4,
        "tails": (4, 5, 6, 6, 8),
    }


def test_count_number_frequency_counts_numbers_and_breaks_ties_by_number():
    draws = [
        Draw("1", date(2026, 1, 1), (1, 2, 3, 4, 5), 0),
        Draw("2", date(2026, 1, 2), (1, 2, 6, 7, 8), 0),
    ]

    assert list(count_number_frequency(draws).items()) == [
        (1, 2),
        (2, 2),
        (3, 1),
        (4, 1),
        (5, 1),
        (6, 1),
        (7, 1),
        (8, 1),
    ]


def test_load_draws_reads_sqlite_history_in_chronological_order(tmp_path):
    db_path = tmp_path / "lotto-539.db"
    with sqlite3.connect(db_path) as conn:
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
                ("115000002", "115/01/02", "06 07 08 09 10", 1),
                ("115000001", "115/01/01", "01 02 03 04 05", 0),
            ],
        )

    assert load_draws(db_path) == [
        Draw("115000001", date(2026, 1, 1), (1, 2, 3, 4, 5), 0),
        Draw("115000002", date(2026, 1, 2), (6, 7, 8, 9, 10), 1),
    ]
