# Lotto 539 Single-Page Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local single-page dashboard for Lotto 539 summary, backtesting, and manual crawl.

**Architecture:** Add `app.py` as a standard-library HTTP server with reusable pure-ish helper functions for tests. Keep existing CLI modules as the source of truth: `lotto_analysis.py` loads and summarizes draw data, `backtest.py` runs strategies, and `fetch_lotto539_history.py` crawls and saves records. Serve a single operational HTML page with embedded CSS and JavaScript from `app.py`.

**Tech Stack:** Python 3 standard library HTTP server, SQLite, existing pytest suite, vanilla HTML/CSS/JavaScript.

---

## File Structure

- Create `app.py`: local HTTP server, JSON API helpers, embedded HTML page.
- Create `test_app.py`: tests summary API helper, backtest API helper, validation, and crawl helper without network access.
- Modify no existing production modules unless tests expose a small integration issue.

### Task 1: Summary API Helper

**Files:**
- Create: `test_app.py`
- Create: `app.py`

- [ ] **Step 1: Write failing tests**

Create `test_app.py` with temporary database helpers and summary assertions:

```python
from datetime import date
import sqlite3

import pytest

from app import (
    BadRequestError,
    build_backtest_response,
    build_summary,
    run_crawl,
)


def create_history_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            '''
            CREATE TABLE history (
                "期別" TEXT PRIMARY KEY,
                "開獎日" TEXT NOT NULL,
                "大小順序" TEXT NOT NULL,
                "頭獎中獎注數" INTEGER NOT NULL
            )
            '''
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_app.py::test_build_summary_returns_database_status_recent_draws_and_frequency -v`

Expected: FAIL because `app.py` does not exist.

- [ ] **Step 3: Implement minimal summary helper**

Create `app.py` with `BadRequestError`, draw serialization, and `build_summary(db_path)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_app.py::test_build_summary_returns_database_status_recent_draws_and_frequency -v`

Expected: PASS.

### Task 2: Backtest API Helper

**Files:**
- Modify: `test_app.py`
- Modify: `app.py`

- [ ] **Step 1: Add failing tests**

Append to `test_app.py`:

```python
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
    assert response["hit_distribution"] == {"0": 1, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest test_app.py -v`

Expected: FAIL because `build_backtest_response()` is missing.

- [ ] **Step 3: Implement minimal backtest helper**

Add validation, date parsing, `BacktestConfig` creation, `run_backtest()` call, and JSON-safe serialization.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest test_app.py -v`

Expected: PASS for summary and backtest helper tests.

### Task 3: Crawl Helper

**Files:**
- Modify: `test_app.py`
- Modify: `app.py`

- [ ] **Step 1: Add failing test**

Append to `test_app.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_app.py::test_run_crawl_uses_injected_fetcher_and_saves_records -v`

Expected: FAIL because `run_crawl()` lacks fetcher injection.

- [ ] **Step 3: Implement minimal crawl helper**

Add `run_crawl(db_path, fetcher=None)` where the default fetcher uses `build_default_url()`, `fetch_html()`, and `parse_history()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_app.py -v`

Expected: PASS.

### Task 4: HTTP Server and Single Page

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add HTTP server and embedded page**

Implement:

- `DASHBOARD_HTML`
- `DashboardRequestHandler`
- `create_handler(db_path)`
- `main()`

The page must call `/api/summary`, `/api/backtest`, and `/api/crawl`, and render summary cards, backtest controls, results, frequency list, and recent draw table.

- [ ] **Step 2: Run app helper tests**

Run: `pytest test_app.py -v`

Expected: PASS.

### Task 5: Full Verification

**Files:**
- Verify: all files

- [ ] **Step 1: Run complete tests**

Run: `pytest -v`

Expected: all tests pass.

- [ ] **Step 2: Start local server**

Run: `Start-Process -WindowStyle Hidden python -ArgumentList 'app.py --port 8000' -PassThru`

Expected: process starts and serves `http://127.0.0.1:8000`.

- [ ] **Step 3: Browser verify**

Use the in-app browser to open `http://127.0.0.1:8000`, confirm visible dashboard content, run a frequency backtest, and confirm results render.

- [ ] **Step 4: Stop local server**

Stop the process started in Step 2.

- [ ] **Step 5: Commit**

Run:

```bash
git add app.py test_app.py
git commit -m "feat: add single page lotto dashboard"
```
